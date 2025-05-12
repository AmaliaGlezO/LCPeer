import socket
import threading
import uuid
import os
from datetime import datetime

class LCPClient:
    def __init__(self, user_id):
        self.user_id = user_id.ljust(20)[:20].encode('utf-8')  # Asegurar 20 bytes
        self.peers = {}  # {peer_id: (ip, port)}
        self.running = True
        self.message_history = []
        
        # Configurar sockets
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_socket.bind(('0.0.0.0', 9990))  # Escuchar en todas las interfaces
        
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_socket.bind(('0.0.0.0', 9990))
        self.tcp_socket.listen(5)
        
        # Iniciar hilos
        threading.Thread(target=self._udp_listener, daemon=True).start()
        threading.Thread(target=self._tcp_listener, daemon=True).start()
        threading.Thread(target=self._discovery_broadcast, daemon=True).start()
    
    def _discovery_broadcast(self):
        """Envía periódicamente paquetes Echo para descubrir usuarios"""
        while self.running:
            print("Enviando paquete de descubrimiento...")
            header = self._build_header(operation=0, user_to=b'\xFF'*20)
            self.udp_socket.sendto(header, ('255.255.255.255', 9990))  # Broadcast
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
    
    def _process_udp_packet(self, data, addr):
        """Procesa un paquete UDP recibido"""
        if len(data) < 100:  # El header debe tener al menos 100 bytes
            print("Paquete recibido es demasiado corto, ignorando.")
            return
        
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
                self.peers[peer_id] = addr
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
                except Exception as e:
                    print(f"Error receiving message body: {e}")
        
        elif operation == 2:  # Transferencia de archivo
            if user_to == b'\xFF'*20 or user_to == self.user_id:
                file_id = data[41]
                file_length = int.from_bytes(data[42:50], 'big')
                
                # Enviar ACK
                response = self._build_response(status=0)
                self.udp_socket.sendto(response, addr)
                
                # El archivo vendrá por TCP (manejado en _handle_tcp_connection)
    
    def _handle_tcp_connection(self, conn, addr):
        """Maneja una conexión TCP entrante (para archivos)"""
        try:
            # Recibir los primeros 8 bytes (ID del archivo)
            file_id = conn.recv(8)
            if not file_id:
                return
            
            # Recibir el resto del archivo
            file_data = file_id + conn.recv(1024*1024)  # Asumimos archivos de hasta 1MB para simplificar
            
            # Guardar archivo
            filename = f"received_file_{int.from_bytes(file_id, 'big')}.dat"
            with open(filename, 'wb') as f:
                f.write(file_data[8:])  # Saltar los 8 bytes del ID
            
            print(f"\nFile received from {addr}: saved as {filename}")
            
            # Enviar confirmación
            response = self._build_response(status=0)
            conn.send(response)
        except Exception as e:
            print(f"Error handling TCP connection: {e}")
        finally:
            conn.close()
    
    def send_message(self, peer_id, message):
        """Envía un mensaje a un peer específico"""
        print(f"Intentando enviar mensaje a {peer_id}: {message}")
        if peer_id not in self.peers:
            print(f"Peer {peer_id} no encontrado")
            return
        
        # Generar ID único para el mensaje
        body_id = uuid.uuid4().int & (1<<64)-1  # 8 bytes
        print(f"ID del cuerpo del mensaje generado: {body_id}")

        # Construir y enviar header
        header = self._build_header(
            operation=1,
            user_to=peer_id.ljust(20)[:20].encode('utf-8'),
            body_id=body_id,
            body_length=len(message.encode('utf-8')))
        
        print(f"Header construido: {header}")
        addr = self.peers[peer_id]
        self.udp_socket.sendto(header, addr)
        print("Header enviado.")

        # Esperar ACK
        try:
            self.udp_socket.settimeout(5)
            ack, _ = self.udp_socket.recvfrom(25)
            print(f"ACK recibido: {ack}")
            if ack[0] == 0:  # OK
                # Enviar cuerpo del mensaje
                body = body_id.to_bytes(8, 'big') + message.encode('utf-8')
                print(f"Enviando cuerpo del mensaje: {body}")
                self.udp_socket.sendto(body, addr)
                print("Cuerpo del mensaje enviado.")
                
                # Esperar confirmación final
                self.udp_socket.settimeout(5)
                final_ack, _ = self.udp_socket.recvfrom(25)
                print(f"Confirmación final recibida: {final_ack}")
                if final_ack[0] == 0:
                    print(f"Mensaje enviado a {peer_id}")
                    self.message_history.append((self.user_id.decode('utf-8').strip(), message, datetime.now()))
                else:
                    print(f"Falló el envío del mensaje a {peer_id}")
        except socket.timeout:
            print(f"Timeout esperando ACK de {peer_id}")
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
        
        # Generar ID único para el archivo
        file_id = uuid.uuid4().int & (1<<64)-1  # 8 bytes
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
            self.udp_socket.settimeout(5)
            ack, _ = self.udp_socket.recvfrom(25)
            if ack[0] == 0:  # OK
                # Establecer conexión TCP y enviar archivo
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect(addr)
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
        return bytes(header)
    
    def _build_response(self, status, response_id=None):
        """Construye una respuesta de 25 bytes según especificación LCP"""
        response = bytearray(25)
        response[0] = status  # ResponseStatus
        if response_id:
            response[1:21] = response_id.ljust(20)[:20].encode('utf-8')  # ResponseId
        # El resto (4 bytes) son reservados
        return bytes(response)
    
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