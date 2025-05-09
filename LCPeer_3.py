#!/usr/bin/env python3
import socket
import threading
import uuid
import os
import subprocess
from datetime import datetime

class LCPClient:
    def __init__(self, user_id):
        self.user_id = user_id.ljust(20)[:20].encode('utf-8')
        self.peers = {}  # {peer_id: (ip, port)}
        self.running = True
        self.message_history = []
        
        # Obtener información de red usando comandos bash
        self.local_ip = self._get_local_ip()
        self.network_info = self._get_network_info()
        
        print(f"Starting LCP client for user: {user_id}")
        print(f"Local IP: {self.local_ip}")
        print(f"Network info: {self.network_info}")
        
        # Configurar sockets
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.udp_socket.bind(('0.0.0.0', 9990))
        
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_socket.bind(('0.0.0.0', 9990))
        self.tcp_socket.listen(5)
        
        # Iniciar hilos
        threading.Thread(target=self._udp_listener, daemon=True).start()
        threading.Thread(target=self._tcp_listener, daemon=True).start()
        threading.Thread(target=self._discovery_broadcast, daemon=True).start()
    
    def _get_local_ip(self):
        """Obtiene la IP local usando comandos bash"""
        try:
            result = subprocess.run(['hostname', '-I'], stdout=subprocess.PIPE)
            return result.stdout.decode('utf-8').split()[0]
        except:
            return '127.0.0.1'
    
    def _get_network_info(self):
        """Obtiene información de red usando ifconfig"""
        try:
            result = subprocess.run(['ifconfig'], stdout=subprocess.PIPE)
            return result.stdout.decode('utf-8')
        except:
            return "Network info not available"
    
    def _get_broadcast_address(self):
        """Intenta obtener la dirección de broadcast de la red"""
        try:
            # Esto puede variar según la distribución Linux
            result = subprocess.run(['ip', 'route'], stdout=subprocess.PIPE)
            lines = result.stdout.decode('utf-8').split('\n')
            for line in lines:
                if 'dev' in line and 'src' in line:
                    parts = line.split()
                    broadcast_idx = parts.index('broadcast') + 1
                    return parts[broadcast_idx]
            return '255.255.255.255'
        except:
            return '255.255.255.255'
    
    def _discovery_broadcast(self):
        """Envía periódicamente paquetes Echo para descubrir usuarios"""
        broadcast_addr = self._get_broadcast_address()
        print(f"Using broadcast address: {broadcast_addr}")
        
        while self.running:
            try:
                header = self._build_header(operation=0, user_to=b'\xFF'*20)
                self.udp_socket.sendto(header, (broadcast_addr, 9990))
                print(f"Discovery packet sent to {broadcast_addr}")
            except Exception as e:
                print(f"Error sending discovery packet: {e}")
            
            threading.Event().wait(5)
    
    def _udp_listener(self):
        """Escucha mensajes UDP entrantes"""
        while self.running:
            try:
                data, addr = self.udp_socket.recvfrom(1024)
                self._process_udp_packet(data, addr)
            except Exception as e:
                if self.running:  # Solo imprimir errores si no estamos cerrando
                    print(f"Error en UDP listener: {e}")
    
    def _tcp_listener(self):
        """Escucha conexiones TCP entrantes (para archivos)"""
        while self.running:
            try:
                conn, addr = self.tcp_socket.accept()
                threading.Thread(target=self._handle_tcp_connection, args=(conn, addr)).start()
            except Exception as e:
                if self.running:
                    print(f"Error en TCP listener: {e}")
    
    def _process_udp_packet(self, data, addr):
        """Procesa un paquete UDP recibido"""
        if len(data) < 100:
            return
        
        try:
            user_from = data[:20].strip(b'\x00').decode('utf-8')
            user_to = data[20:40]
            operation = data[40]
            
            print(f"\nPacket received from {user_from}@{addr}: Operation {operation}")
            
            if operation == 0:  # Echo (descubrimiento)
                if user_from != self.user_id.strip(b'\x00').decode('utf-8'):
                    response = self._build_response(status=0)
                    self.udp_socket.sendto(response, addr)
                    
                    if user_from not in self.peers or self.peers[user_from] != addr:
                        self.peers[user_from] = addr
                        print(f"New peer discovered: {user_from} at {addr}")
            
            elif operation == 1:  # Mensaje
                if user_to == b'\xFF'*20 or user_to == self.user_id:
                    body_id = data[41]
                    body_length = int.from_bytes(data[42:50], 'big')
                    
                    response = self._build_response(status=0)
                    self.udp_socket.sendto(response, addr)
                    
                    try:
                        body_data, _ = self.udp_socket.recvfrom(body_length + 8)
                        if len(body_data) >= 8 and body_data[:8] == body_id.to_bytes(8, 'big'):
                            message = body_data[8:].decode('utf-8')
                            self.message_history.append((user_from, message, datetime.now()))
                            print(f"\n[New Message] {user_from}: {message}")
                            self.udp_socket.sendto(response, addr)
                    except Exception as e:
                        print(f"Error receiving message body: {e}")
            
            elif operation == 2:  # Transferencia de archivo
                if user_to == b'\xFF'*20 or user_to == self.user_id:
                    file_id = data[41]
                    file_length = int.from_bytes(data[42:50], 'big')
                    
                    response = self._build_response(status=0)
                    self.udp_socket.sendto(response, addr)
                    print(f"File transfer initiated from {user_from}, waiting for TCP connection...")
        
        except Exception as e:
            print(f"Error processing UDP packet: {e}")
    
    def _handle_tcp_connection(self, conn, addr):
        """Maneja una conexión TCP entrante (para archivos)"""
        try:
            file_id = conn.recv(8)
            if not file_id:
                return
            
            file_data = b''
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                file_data += chunk
            
            filename = f"received_file_{int.from_bytes(file_id, 'big')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.dat"
            with open(filename, 'wb') as f:
                f.write(file_data)
            
            print(f"\n[File Received] Saved as {filename} from {addr}")
            
            response = self._build_response(status=0)
            conn.send(response)
        except Exception as e:
            print(f"Error handling TCP connection: {e}")
        finally:
            conn.close()
    
    def send_message(self, peer_id, message):
        """Envía un mensaje a un peer específico"""
        if peer_id not in self.peers:
            print(f"Peer {peer_id} not found in discovered peers")
            return
        
        body_id = uuid.uuid4().int & (1<<64)-1
        header = self._build_header(
            operation=1,
            user_to=peer_id.ljust(20)[:20].encode('utf-8'),
            body_id=body_id,
            body_length=len(message.encode('utf-8')))
        
        addr = self.peers[peer_id]
        
        try:
            self.udp_socket.sendto(header, addr)
            self.udp_socket.settimeout(5)
            
            ack, _ = self.udp_socket.recvfrom(25)
            if ack[0] == 0:
                body = body_id.to_bytes(8, 'big') + message.encode('utf-8')
                self.udp_socket.sendto(body, addr)
                
                final_ack, _ = self.udp_socket.recvfrom(25)
                if final_ack[0] == 0:
                    print(f"Message successfully sent to {peer_id}")
                    self.message_history.append((self.user_id.decode('utf-8').strip(), message, datetime.now()))
                else:
                    print(f"Final ACK failed from {peer_id}")
            else:
                print(f"Initial ACK failed from {peer_id}")
        except socket.timeout:
            print(f"Timeout waiting for response from {peer_id}")
        except Exception as e:
            print(f"Error sending message: {e}")
        finally:
            self.udp_socket.settimeout(None)
    
    def send_file(self, peer_id, filepath):
        """Envía un archivo a un peer específico"""
        if peer_id not in self.peers:
            print(f"Peer {peer_id} not found")
            return
        
        if not os.path.exists(filepath):
            print(f"File {filepath} not found")
            return
        
        file_id = uuid.uuid4().int & (1<<64)-1
        file_size = os.path.getsize(filepath)
        
        header = self._build_header(
            operation=2,
            user_to=peer_id.ljust(20)[:20].encode('utf-8'),
            body_id=file_id,
            body_length=file_size)
        
        addr = self.peers[peer_id]
        
        try:
            self.udp_socket.sendto(header, addr)
            self.udp_socket.settimeout(5)
            
            ack, _ = self.udp_socket.recvfrom(25)
            if ack[0] == 0:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(10)
                    s.connect(addr)
                    
                    # Enviar ID del archivo
                    s.send(file_id.to_bytes(8, 'big'))
                    
                    # Enviar archivo en chunks
                    with open(filepath, 'rb') as f:
                        while True:
                            chunk = f.read(4096)
                            if not chunk:
                                break
                            s.send(chunk)
                    
                    # Esperar confirmación
                    final_ack = s.recv(25)
                    if final_ack[0] == 0:
                        print(f"File successfully sent to {peer_id}")
                    else:
                        print(f"File transfer failed with error code {final_ack[0]}")
            else:
                print(f"Initial ACK failed from {peer_id}")
        except socket.timeout:
            print(f"Timeout during file transfer to {peer_id}")
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
        return bytes(header)
    
    def _build_response(self, status, response_id=None):
        """Construye una respuesta de 25 bytes según especificación LCP"""
        response = bytearray(25)
        response[0] = status  # ResponseStatus
        if response_id:
            response[1:21] = response_id.ljust(20)[:20].encode('utf-8')  # ResponseId
        return bytes(response)
    
    def shutdown(self):
        """Cierra limpiamente el cliente"""
        self.running = False
        try:
            self.udp_socket.close()
        except:
            pass
        try:
            self.tcp_socket.close()
        except:
            pass

def clear_screen():
    """Limpia la pantalla usando comando bash"""
    os.system('clear')

def show_banner():
    """Muestra un banner informativo"""
    clear_screen()
    print("\n" + "="*50)
    print("   LCP Chat Client - Linux Edition")
    print("="*50 + "\n")

def main():
    show_banner()
    user_id = input("Enter your user ID (max 20 chars): ").strip()
    if not user_id:
        user_id = "user_" + str(uuid.uuid4())[:8]
    
    client = LCPClient(user_id)
    
    try:
        while True:
            print("\nOptions:")
            print("1. List discovered peers")
            print("2. Send message to peer")
            print("3. Send file to peer")
            print("4. Show message history")
            print("5. Network information")
            print("6. Exit")
            
            choice = input("\nSelect an option (1-6): ").strip()
            
            if choice == "1":
                clear_screen()
                print("\nDiscovered peers:")
                if not client.peers:
                    print("No peers discovered yet...")
                else:
                    for i, (peer_id, addr) in enumerate(client.peers.items(), 1):
                        print(f"{i}. {peer_id} at {addr}")
            
            elif choice == "2":
                clear_screen()
                if not client.peers:
                    print("No peers available to send messages")
                    continue
                
                print("Select a peer to message:")
                peers = list(client.peers.items())
                for i, (peer_id, addr) in enumerate(peers, 1):
                    print(f"{i}. {peer_id}")
                
                try:
                    peer_num = int(input("\nEnter peer number: ")) - 1
                    if 0 <= peer_num < len(peers):
                        peer_id, _ = peers[peer_num]
                        message = input("Enter your message: ")
                        client.send_message(peer_id, message)
                    else:
                        print("Invalid peer number")
                except ValueError:
                    print("Please enter a valid number")
            
            elif choice == "3":
                clear_screen()
                if not client.peers:
                    print("No peers available to send files")
                    continue
                
                print("Select a peer to send file:")
                peers = list(client.peers.items())
                for i, (peer_id, addr) in enumerate(peers, 1):
                    print(f"{i}. {peer_id}")
                
                try:
                    peer_num = int(input("\nEnter peer number: ")) - 1
                    if 0 <= peer_num < len(peers):
                        peer_id, _ = peers[peer_num]
                        filepath = input("Enter full path to file: ").strip()
                        if os.path.exists(filepath):
                            client.send_file(peer_id, filepath)
                        else:
                            print("File not found")
                    else:
                        print("Invalid peer number")
                except ValueError:
                    print("Please enter a valid number")
            
            elif choice == "4":
                clear_screen()
                print("\nMessage History:")
                if not client.message_history:
                    print("No messages yet")
                else:
                    for sender, message, timestamp in client.message_history:
                        print(f"[{timestamp.strftime('%H:%M:%S')}] {sender}: {message}")
            
            elif choice == "5":
                clear_screen()
                print("\nNetwork Information:")
                print(f"Local IP: {client.local_ip}")
                print("\nInterface Configuration:")
                print(client.network_info)
            
            elif choice == "6":
                break
            
            else:
                print("Invalid option, please try again")
    
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        client.shutdown()

if __name__ == "__main__":
    main()