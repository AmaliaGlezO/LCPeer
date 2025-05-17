import socket
import threading
import uuid
import os
from datetime import datetime
import queue
import subprocess
import re
import ipaddress
import time

def get_ip_and_mask():
    """Obtiene la IP y máscara de red de la interfaz activa (multi-plataforma)"""
    try:
        # Para Windows
        result = subprocess.run(['ipconfig'], capture_output=True, text=True)
        output = result.stdout
        ip_match = re.search(r"IPv4 Address[ .]*: (\d+\.\d+\.\d+\.\d+)", output) or \
                   re.search(r"Dirección IPv4[ .]*: (\d+\.\d+\.\d+\.\d+)", output)
        mask_match = re.search(r"Subnet Mask[ .]*: (\d+\.\d+\.\d+\.\d+)", output) or \
                     re.search(r"Máscara de subred[ .]*: (\d+\.\d+\.\d+\.\d+)", output)
        
        if ip_match and mask_match:
            return ip_match.group(1), mask_match.group(1)
        
        # Para Linux/macOS
        result = subprocess.run(['ifconfig'], capture_output=True, text=True)
        output = result.stdout
        ip_match = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", output)
        mask_match = re.search(r"netmask (\d+\.\d+\.\d+\.\d+)", output)
        
        if ip_match and mask_match:
            return ip_match.group(1), mask_match.group(1)
            
    except Exception as e:
        print(f"Error getting network info: {e}")
    
    return None, None

def calcular_broadcast(ip, mask):
    """Calcula la dirección de broadcast para la red"""
    try:
        if ip and mask:
            network = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
            return str(network.broadcast_address)
    except Exception as e:
        print(f"Error calculating broadcast: {e}")
    return '255.255.255.255'

class LCPClient:
    def __init__(self, user_id):
        self.user_id = user_id.ljust(20)[:20].encode('utf-8')
        self.peers = {}  # {peer_id: (ip, port)}
        self.running = True
        self.message_history = []  # (sender, message, timestamp)
        self.response_queue = queue.Queue()
        
        # Configurar socket UDP para mensajes de control
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_socket.bind(('0.0.0.0', 9990))
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65507)
        
        # Configurar socket TCP para transferencia de archivos
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_socket.bind(('0.0.0.0', 9990))
        self.tcp_socket.listen(5)
        
        # Iniciar hilos para escuchar conexiones
        threading.Thread(target=self._udp_listener, daemon=True).start()
        threading.Thread(target=self._tcp_listener, daemon=True).start()
        
        # Iniciar descubrimiento automático de peers
        self._start_autodiscovery()

    def _start_autodiscovery(self):
        """Inicia el proceso de descubrimiento automático de peers"""
        # Hilo para enviar broadcasts periódicos
        threading.Thread(target=self._discovery_broadcast, daemon=True).start()
        
        # Hilo para limpieza periódica de peers inactivos
        threading.Thread(target=self._clean_inactive_peers, daemon=True).start()

    def _discovery_broadcast(self):
        """Envía mensajes de descubrimiento periódicamente"""
        ip, mask = get_ip_and_mask()
        broadcast_addr = calcular_broadcast(ip, mask)
        
        while self.running:
            try:
                # Construir y enviar header de descubrimiento según LCP
                header = self._build_header(
                    operation=0,  # Operation 0: Echo-Reply (Discovery)
                    user_to=b'\xFF'*20  # Broadcast address
                )
                
                self.udp_socket.sendto(header, (broadcast_addr, 9990))
                time.sleep(5)  # Enviar cada 5 segundos
                
            except Exception as e:
                print(f"Error in discovery broadcast: {e}")
                time.sleep(5)

    def _clean_inactive_peers(self):
        """Limpia peers que no han respondido en los últimos 30 segundos"""
        while self.running:
            try:
                current_time = time.time()
                inactive_peers = []
                
                for peer_id, (_, _, last_seen) in list(self.peers.items()):
                    if current_time - last_seen > 30:  # 30 segundos de inactividad
                        inactive_peers.append(peer_id)
                
                for peer_id in inactive_peers:
                    del self.peers[peer_id]
                    print(f"Removed inactive peer: {peer_id}")
                
                time.sleep(10)  # Revisar cada 10 segundos
                
            except Exception as e:
                print(f"Error cleaning inactive peers: {e}")
                time.sleep(10)

    def _udp_listener(self):
        """Escucha mensajes UDP entrantes"""
        while self.running:
            try:
                data, addr = self.udp_socket.recvfrom(1024)
                self._process_udp_packet(data, addr)
            except Exception as e:
                if self.running:  # Solo imprimir errores si no estamos cerrando
                    print(f"Error in UDP listener: {e}")

    def _tcp_listener(self):
        """Escucha conexiones TCP entrantes para transferencia de archivos"""
        while self.running:
            try:
                conn, addr = self.tcp_socket.accept()
                threading.Thread(
                    target=self._handle_tcp_connection,
                    args=(conn, addr),
                    daemon=True
                ).start()
            except Exception as e:
                if self.running:
                    print(f"Error in TCP listener: {e}")

    def normalizar(self, name):
        """Normaliza nombres de peers eliminando padding y nulos"""
        return name.strip().rstrip('\x00')

    def _process_udp_packet(self, data, addr):
        """Procesa paquetes UDP según el protocolo LCP"""
        try:
            if len(data) < 41:  # Tamaño mínimo del header según LCP
                return

            user_from = self.normalizar(data[:20].decode('utf-8', errors='ignore'))
            user_to = data[20:40]
            operation = data[40]

            # Ignorar mensajes de nosotros mismos
            if user_from == self.normalizar(self.user_id.decode('utf-8')):
                return

            # Operación 0: Descubrimiento (Echo-Reply)
            if operation == 0:
                # Responder según LCP (ResponseStatus=0)
                response = self._build_response(status=0)
                self.udp_socket.sendto(response, addr)
                
                # Actualizar lista de peers
                if user_from not in self.peers or self.peers[user_from][:2] != (addr[0], 9990):
                    print(f"Discovered new peer: {user_from} at {addr[0]}:9990")
                
                # Guardar peer con marca de tiempo
                self.peers[user_from] = (addr[0], 9990, time.time())

            # Operación 1: Mensaje de texto
            elif operation == 1:
                # Verificar si el mensaje es para nosotros o broadcast
                if user_to == b'\xFF'*20 or user_to == self.user_id:
                    body_id = data[41]
                    body_length = int.from_bytes(data[42:50], 'big')
                    
                    # Responder OK según LCP
                    response = self._build_response(status=0)
                    self.udp_socket.sendto(response, addr)
                    
                    try:
                        # Recibir cuerpo del mensaje
                        body_data, _ = self.udp_socket.recvfrom(body_length + 8)
                        if len(body_data) >= 8 and body_data[:8] == body_id.to_bytes(8, 'big'):
                            message = body_data[8:].decode('utf-8', errors='ignore')
                            timestamp = datetime.now()
                            
                            # Agregar a historial
                            self.message_history.append((user_from, message, timestamp))
                            print(f"Message from {user_from}: {message}")
                            
                            # Confirmar recepción según LCP
                            self.udp_socket.sendto(response, addr)
                            self.response_queue.put((addr, response))
                            
                            # Actualizar peer como activo
                            if user_from in self.peers:
                                self.peers[user_from] = (addr[0], 9990, time.time())
                    except Exception as e:
                        print(f"Error receiving message body: {e}")

        except Exception as e:
            print(f"Error processing UDP packet: {e}")

    def _handle_tcp_connection(self, conn, addr):
        """Maneja conexiones TCP para transferencia de archivos"""
        try:
            # Recibir los primeros 8 bytes (ID del archivo)
            file_id = conn.recv(8)
            if not file_id:
                return
                
            # Recibir el resto del archivo
            file_data = file_id + conn.recv(1024*1024)  # Buffer de 1MB
            
            # Guardar archivo
            filename = f"received_file_{int.from_bytes(file_id, 'big')}.dat"
            with open(filename, 'wb') as f:
                f.write(file_data[8:])
            
            print(f"File received from {addr}: {filename}")
            
            # Responder OK según LCP
            response = self._build_response(status=0)
            conn.send(response)
            
        except Exception as e:
            print(f"Error handling TCP connection: {e}")
        finally:
            conn.close()


    def send_message_to_all(self, message):
        """Envía un mensaje a todos los peers conectados."""
        for peer_id in self.peers.keys():
            self.send_message(peer_id, message)

    def send_message(self, peer_id, message):
        """Envía un mensaje a un peer específico o a todos si peer_id es None."""
        if peer_id is None:
            self.send_message_to_all(message)
            return
        
        if peer_id == chr(255)*20:
            ip, mask = get_ip_and_mask()
            broadcast = calcular_broadcast(ip, mask) or '255.255.255.255'
            addr = (broadcast, 9990)
        else:
            if self.normalizar(peer_id) not in self.peers:
                print(f"Peer {peer_id} no encontrado")
                return
            addr = self.peers[peer_id]

        body_id = uuid.uuid4().int % 256
        header = self._build_header(
            operation=1,
            user_to=peer_id.ljust(20)[:20].encode('utf-8') if peer_id != chr(255)*20 else b'\xFF'*20,
            body_id=body_id,
            body_length=len(message.encode('utf-8'))
        )
        self.udp_socket.sendto(header, addr)
        try:
            self.udp_socket.settimeout(5)
            ack = self.response_queue.get()
            if ack[0] == 0:
                body = body_id.to_bytes(8, 'big') + message.encode('utf-8')
                self.udp_socket.sendto(body, addr)
                final_ack, _ = self.udp_socket.recvfrom(25)
                if final_ack[0] == 0:
                    self.message_history.append((self.user_id.decode('utf-8').strip(), message, datetime.now()))
        except queue.Empty:
            print(f"Timeout esperando ACK de {peer_id}")
        finally:
            self.udp_socket.settimeout(None)

    def send_file(self, peer_id, filepath):
        if peer_id not in self.peers:
            print(f"Peer {peer_id} not found")
            return
        if not os.path.exists(filepath):
            print(f"File {filepath} not found")
            return
        file_id = uuid.uuid4().int % 256
        file_size = os.path.getsize(filepath)
        header = self._build_header(
            operation=2,
            user_to=peer_id.ljust(20)[:20].encode('utf-8'),
            body_id=file_id,
            body_length=file_size
        )
        addr = self.peers[peer_id]
        self.udp_socket.sendto(header, addr)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(addr)
                with open(filepath, 'rb') as f:
                    s.send(file_id.to_bytes(8, 'big'))
                    s.sendfile(f)
                s.settimeout(5)
                final_ack = s.recv(25)
                if final_ack[0] == 0:
                    print(f"File sent to {peer_id}")
        except Exception as e:
            print(f"Error sending file: {e}")

    def _build_header(self, operation, user_to, body_id=0, body_length=0):
        """Construye el header según especificación LCP"""
        header = bytearray(100)
        header[0:20] = self.user_id
        header[20:40] = user_to
        header[40] = operation
        header[41] = body_id
        header[42:50] = body_length.to_bytes(8, 'big')
        return bytes(header)

    def _build_response(self, status, response_id=None):
        """Construye respuesta según especificación LCP"""
        response = bytearray(25)
        response[0] = status
        if response_id:
            response[1:21] = response_id.ljust(20)[:20].encode('utf-8')
        return bytes(response)

    def shutdown(self):
        """Cierra todas las conexiones y detiene los hilos"""
        self.running = False
        try:
            self.udp_socket.close()
        except:
            pass
        try:
            self.tcp_socket.close()
        except:
            pass

def main():
    user_id = input("Enter your user ID (max 20 chars): ")
    client = LCPClient(user_id)
    
    try:
        while True:
            print("\nOptions:")
            print("1. List peers")
            print("2. Send message")
            print("3. Send file")
            print("4. Show message history")
            print("5. Exit")
            
            choice = input("Choose an option: ")
            
            if choice == "1":
                print("\nDiscovered peers:")
                for peer_id, addr in client.peers.items():
                    print(f"- {peer_id} at {addr}")
            
            elif choice == "2":
                peer_id = input("Enter peer ID: ")
                message = input("Enter message: ")
                client.send_message(peer_id, message)
            
            elif choice == "3":
                peer_id = input("Enter peer ID: ")
                filepath = input("Enter file path: ")
                client.send_file(peer_id, filepath)
            
            elif choice == "4":
                print("\nMessage history:")
                for sender, message, timestamp in client.message_history:
                    print(f"[{timestamp}] {sender}: {message}")
            
            elif choice == "5":
                break
            
            else:
                print("Invalid option")
    finally:
        client.shutdown()

if __name__ == "__main__":
    main()