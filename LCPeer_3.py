import socket
import threading
import uuid
import os
from datetime import datetime
import queue
import struct
import subprocess
import re
import ipaddress
import time 
def get_ip_and_mask():
    # Ejecutar ipconfig y capturar la salida
    result = subprocess.run(['ipconfig'], capture_output=True, text=True)
    output = result.stdout

    # Buscar IPv4 y máscara usando expresiones regulares
    ip_match = re.search(r"Dirección IPv4[ .]+: (\d+\.\d+\.\d+\.\d+)", output)
    mask_match = re.search(r"Máscara de subred[ .]+: (\d+\.\d+\.\d+\.\d+)", output)

    if ip_match and mask_match:
        return ip_match.group(1), mask_match.group(1)
    return None, None

def calcular_broadcast(ip, mask):
    if ip and mask:
        network = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
        return str(network.broadcast_address)
    return None


class LCPClient:
    def __init__(self, user_id):
        self.user_id = user_id.ljust(20)[:20].encode('utf-8')  # Asegurar 20 bytes
        self.peers = {}  # {peer_id: (ip, port)}
        self.running = True
        self.message_history = []
        self.response_queue = queue.Queue()  # Cola para respuestas
        
        # Configurar sockets
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_socket.bind(('0.0.0.0', 9990))  # Escuchar en todas las interfaces
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65507)  # Aumentar el búfer de recepción
        
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_socket.bind(('0.0.0.0', 9990))
        self.tcp_socket.listen(5)
        
        # Iniciar hilos
        threading.Thread(target=self._udp_listener, daemon=True).start()
        threading.Thread(target=self._tcp_listener, daemon=True).start()
        threading.Thread(target=self._discovery_broadcast, daemon=True).start()
    
    def _discovery_broadcast(self):
        # Obtener IP y máscara
        ip, mask = get_ip_and_mask()

       
        """Envía periódicamente paquetes Echo para descubrir usuarios"""
        while self.running:
            print("Enviando paquete de descubrimiento...")
            header = self._build_header(operation=0, user_to=b'\xFF'*20)
            
            for i in ['193.168.143.255']:

                self.udp_socket.sendto(header, (i, 9990))  # Broadcast
            print("Paquete de descubrimiento enviado.")
            threading.Event().wait(5)  # Esperar 5 segundos
    
    def _udp_listener(self):
        """Escucha mensajes UDP entrantes"""
        while self.running:
            try:
                data, addr = self.udp_socket.recvfrom(1024)
                self._process_udp_packet(data, addr)
            except Exception as e:
                print(f"Error en UDP listener: {e}")
    
    def _tcp_listener(self):
        """Escucha conexiones TCP entrantes (para archivos)"""
        while self.running:
            try:
                conn, addr = self.tcp_socket.accept()
                threading.Thread(target=self._handle_tcp_connection, args=(conn, addr)).start()
            except Exception as e:
                print(f"Error en TCP listener: {e}")
    def normalizar(self,name):
        return name.strip().rstrip('\x00')
    
    def _process_udp_packet(self, data, addr):
        """Procesa un paquete UDP recibido"""
        if len(data) == 25:  # Cambiar a 25 bytes como mínimo
            print("respuesta recibido")
            self.response_queue.put(data)
            return
        
        # Asegúrate de que el paquete tenga al menos 100 bytes para operaciones que lo requieran
        if len(data) < 100:
            print("Paquete recibido es corto, pero procesando como mensaje.")
        
        user_from = data[:20].strip(b'\x00')
        user_to = data[20:40]
        operation = data[40]
        
        print(f"Paquete recibido de {user_from.decode('utf-8')} con operación {operation}")

        if operation == 0:  # Echo (descubrimiento)
            if user_from != self.user_id.strip(b'\x00'):
                # Responder con nuestro ID
                response = self._build_response(status=0)
                self.udp_socket.sendto(response, addr)
                print(f"Respondido a {user_from.decode('utf-8')} con nuestro ID.")
                
                # Actualizar lista de peers
                peer_id = user_from.decode('utf-8')
                self.peers[self.normalizar(peer_id)] = (addr[0], 9990)
                print(f"Descubierto par: {peer_id} en {addr}")
        
        elif operation == 1:  # Mensaje
            if user_to == b'\xFF'*20 or user_to == self.user_id:
                body_id = data[41]
                body_length = int.from_bytes(data[42:50], 'big')
                
                # Enviar ACK
                response = self._build_response(status=0)
                self.udp_socket.sendto(response, addr)
                
                # Esperar cuerpo del mensaje
                try:
                    body_data, _ = self.udp_socket.recvfrom(body_length + 8)
                    
                    if len(body_data) >= 8 and body_data[:8] == body_id.to_bytes(8, 'big'):
                        message = body_data[8:].decode('utf-8')
                        self.message_history.append((user_from.decode('utf-8'), message, datetime.now()))
                        print(f"\nMessage from {user_from.decode('utf-8')}: {message}")
                        # Enviar confirmación final
                        self.udp_socket.sendto(response, addr)
                        self.response_queue.put(response)  # Colocar respuesta en la cola
                        
                except Exception as e:
                    print(f"Error receiving message body: {e}")
        
        elif operation == 2:  # Transferencia de archivo
            if user_to == b'\xFF'*20 or user_to == self.user_id:
                file_id = data[41]
                file_length = int.from_bytes(data[42:50], 'big')
                self.file = {'file_length':file_length,'file_id':file_id,'user_from':user_from}
                # El archivo vendrá por TCP (manejado en _handle_tcp_connection)
    
    def _handle_tcp_connection(self, conn, addr):
        """Maneja una conexión TCP entrante (para archivos)"""
        try:
            # Recibir los primeros 8 bytes (ID del archivo)
            file_id = conn.recv(8)
            if not file_id:
                print("No se recibió ID del archivo.")
                return

            # Confirmar que el ID del archivo coincide
            print(file_id)
            print(self.file['file_id'].to_bytes(8,'big'))
            if file_id != self.file['file_id'].to_bytes(8,'big'):
                print("ID de archivo no coincide.")
                return

            # Recibir el resto del archivo
            bythes_recibidos = 0
            with open(f'temp_file{time.time()}.dat', 'wb') as f:
                while bythes_recibidos < self.file['file_length']:
                    restantes = self.file['file_length'] - bythes_recibidos
                    chunk_size = min(restantes, 65507)  # Limitar el tamaño del chunk a 65507 bytes

                    data = conn.recv(chunk_size)
                    if not data:
                        print("Conexión cerrada antes de completar la recepción del archivo.")
                        break

                    f.write(data)
                    bythes_recibidos += len(data)

            # Verificar si se recibió el archivo completo
            if bythes_recibidos == self.file['file_length']:
                print(f"\nArchivo recibido de {addr}: guardado como temp_file{time.time()}.dat")
                # Enviar confirmación
                response = self._build_response(status=0)
                conn.send(response)
            else:
                print("Error: archivo recibido incompleto.")
                response = self._build_response(status=1)  # Error
                conn.send(response)
        except Exception as e:
            print(f"Error handling TCP connection: {e}")
        finally:
            conn.close()
    
    def send_message(self, peer_id, message):
        """Envía un mensaje a un peer específico con reintentos"""
        print(f"Intentando enviar mensaje a {peer_id}: {message}")
        if self.normalizar(peer_id) not in self.peers:
            print(f"Peer {peer_id} no encontrado")
            return
        
        # Generar ID único para el mensaje
        body_id = uuid.uuid4().int % 256  # 1 byte
        print(f"ID del cuerpo del mensaje generado: {body_id}")

        # Construir header
        header = self._build_header(
            operation=1,
            user_to=peer_id.ljust(20)[:20].encode('utf-8'),
            body_id=body_id,
            body_length=len(message.encode('utf-8')))
        
        addr = self.peers[peer_id]
        
        # Paso 1: Envío de header y espera de ACK con reintentos
        header_sent = False
        for attempt in range(5):
            try:
                print(f"Intento {attempt + 1}/5: Enviando header...")
                self.udp_socket.sendto(header, addr)
                
                # Esperar ACK con timeout
                self.udp_socket.settimeout(5)
                try:
                    ack = self.response_queue.get(timeout=5)
                    if ack[0] == 0:  # OK
                        print("ACK recibido, procediendo a enviar cuerpo del mensaje")
                        header_sent = True
                        break
                    else:
                        print(f"ACK no válido recibido, reintentando...")
                except queue.Empty:
                    print("Timeout esperando ACK, reintentando...")
            except Exception as e:
                print(f"Error enviando header: {e}, reintentando...")
            finally:
                self.udp_socket.settimeout(None)
        
        if not header_sent:
            print("Fallo después de 5 intentos de enviar header")
            return
        
        # Paso 2: Envío de cuerpo y espera de confirmación final con reintentos
        body = body_id.to_bytes(8, 'big') + message.encode('utf-8')
        message_sent = False
        
        for attempt in range(5):
            try:
                print(f"Intento {attempt + 1}/5: Enviando cuerpo del mensaje...")
                self.udp_socket.sendto(body, addr)
                
                # Esperar confirmación final
                self.udp_socket.settimeout(5)
                try:
                    final_ack = self.response_queue.get(timeout=5)
                    if final_ack[0] == 0:
                        print("Confirmación final recibida, mensaje enviado con éxito")
                        self.message_history.append((self.user_id.decode('utf-8').strip(), message, datetime.now()))
                        message_sent = True
                        break
                    else:
                        print(f"Confirmación no válida recibida, reintentando...")
                except queue.Empty:
                    print("Timeout esperando confirmación final, reintentando...")
            except Exception as e:
                print(f"Error enviando cuerpo del mensaje: {e}, reintentando...")
            finally:
                self.udp_socket.settimeout(None)
        
        if not message_sent:
            print("Fallo después de 5 intentos de enviar mensaje completo")
    
    def send_file(self, peer_id, filepath):
        """Envía un archivo a un peer específico"""
        if peer_id not in self.peers:
            print(f"Peer {peer_id} not found")
            return
        
        if not os.path.exists(filepath):
            print(f"File {filepath} not found")
            return
        
        # Generar ID único para el archivo
        file_id = uuid.uuid4().int %256  # 8 bytes
        file_size = os.path.getsize(filepath)
        
        # Construir y enviar header
        header = self._build_header(
            operation=2,
            user_to=peer_id.ljust(20)[:20].encode('utf-8'),
            body_id=file_id,
            body_length=file_size)
        
        addr = self.peers[peer_id]
        self.udp_socket.sendto(header, addr)
        
        # Esperar ACK
        try:
           
                # Establecer conexión TCP y enviar archivo
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect((addr))
                    with open(filepath, 'rb') as f:
                        # Enviar ID del archivo primero
                        s.send(file_id.to_bytes(8, 'big'))
                        # Enviar contenido del archivo
                        s.sendfile(f)
                    
                    # Esperar confirmación final
                    s.settimeout(5)
                    final_ack = s.recv(25)
                    if final_ack[0] == 0:
                        print(f"File sent to {peer_id}")
                    else:
                        print(f"Failed to send file to {peer_id}")
        except socket.timeout:
            print(f"Timeout waiting for ACK from {peer_id}")
        except Exception as e:
            print(f"Error sending file: {e}")
        finally:
            self.udp_socket.settimeout(None)
    
    def _build_header(self, operation, user_to, body_id=0, body_length=0):
        """Construye el header de 100 bytes según especificación LCP"""
        header = bytearray(100)
        header[0:20] = self.user_id  # UserIdFrom
        header[20:40] = user_to      # UserIdTo
        header[40] = operation       # OperationCode
        header[41] = body_id         # BodyId (1 byte)
        header[42:50] = body_length.to_bytes(8, 'big')  # BodyLength
        # El resto (50 bytes) son reservados
        return header
    
    def _build_response(self, status, response_id=None):
        """Construye una respuesta de 25 bytes según especificación LCP"""
        response = bytearray(25)
        response[0] = status  # ResponseStatus
        if not response_id:
            response[1:21] = self.user_id  # ResponseId
        else:
            response[1:21]=response_id.ljust(20)[:20].encode('utf-8')# El resto (4 bytes) son reservados
        return response
    
    def shutdown(self):
        """Cierra limpiamente el cliente"""
        self.running = False
        self.udp_socket.close()
        self.tcp_socket.close()

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