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
    result = subprocess.run(['ipconfig'], capture_output=True, text=True)
    output = result.stdout
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
        self.user_id = user_id.ljust(20)[:20].encode('utf-8')
        self.peers = {}
        self.running = True
        self.message_history = []
        self.response_queue = queue.Queue()
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_socket.bind(('0.0.0.0', 9990))
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65507)
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_socket.bind(('0.0.0.0', 9990))
        self.tcp_socket.listen(5)
        threading.Thread(target=self._udp_listener, daemon=True).start()
        threading.Thread(target=self._tcp_listener, daemon=True).start()
        threading.Thread(target=self._discovery_broadcast, daemon=True).start()

    def _discovery_broadcast(self):
        ip, mask = get_ip_and_mask()
        broadcast = calcular_broadcast(ip, mask) or '255.255.255.255'
        while self.running:
            header = self._build_header(operation=0, user_to=b'\xFF'*20)
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.udp_socket.sendto(header, (broadcast, 9990))
            time.sleep(5)

    def _udp_listener(self):
        while self.running:
            try:
                data, addr = self.udp_socket.recvfrom(1024)
                self._process_udp_packet(data, addr)
            except Exception as e:
                print(f"Error en UDP listener: {e}")

    def _tcp_listener(self):
        while self.running:
            try:
                conn, addr = self.tcp_socket.accept()
                threading.Thread(target=self._handle_tcp_connection, args=(conn, addr)).start()
            except Exception as e:
                print(f"Error en TCP listener: {e}")

    def normalizar(self, name):
        return name.strip().rstrip('\x00')

    def _process_udp_packet(self, data, addr):
        if len(data) == 25:
            self.response_queue.put(data)
            return
        if len(data) < 100:
            return
        user_from = data[:20].strip(b'\x00').decode('utf-8')
        user_to = data[20:40]
        operation = data[40]

        if operation == 0:
            if user_from != self.user_id.strip(b'\x00').decode('utf-8'):
                response = self._build_response(status=0)
                self.udp_socket.sendto(response, addr)
                self.peers[self.normalizar(user_from)] = (addr[0], 9990)

        elif operation == 1:
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
                        self.udp_socket.sendto(response, addr)
                        self.response_queue.put((addr, response))
                except Exception as e:
                    print(f"Error receiving message body: {e}")

    def _handle_tcp_connection(self, conn, addr):
        try:
            file_id = conn.recv(8)
            if not file_id:
                return
            file_data = file_id + conn.recv(1024*1024)
            filename = f"received_file_{int.from_bytes(file_id, 'big')}.dat"
            with open(filename, 'wb') as f:
                f.write(file_data[8:])
            response = self._build_response(status=0)
            conn.send(response)
        except Exception as e:
            print(f"Error handling TCP connection: {e}")
        finally:
            conn.close()

    def send_message(self, peer_id, message):
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
        header = bytearray(100)
        header[0:20] = self.user_id
        header[20:40] = user_to
        header[40] = operation
        header[41] = body_id
        header[42:50] = body_length.to_bytes(8, 'big')
        return bytes(header)

    def _build_response(self, status, response_id=None):
        response = bytearray(25)
        response[0] = status
        if response_id:
            response[1:21] = response_id.ljust(20)[:20].encode('utf-8')
        return bytes(response)

    def shutdown(self):
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