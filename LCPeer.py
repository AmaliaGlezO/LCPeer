import socket
import threading
import time
from typing import Dict, List, Optional
import subprocess
import platform
import re



def get_info():
    broadcast_addresses = []
    system = platform.system()
    
    if system == "Windows":
        try:
            # Ejecutar ipconfig con codificación correcta para Windows en español
            output = subprocess.check_output(["ipconfig"], universal_newlines=True, encoding='cp437')
            sections = output.split("\n\n")
            
            for section in sections:
                # Buscar sección con dirección IPv4 (manejando caracteres mal interpretados)
                if "Direcci" in section and ("IPv4" in section or "IP4" in section):
                    # Expresiones regulares más robustas para el formato mostrado
                    ip_match = re.search(r'Direcci.n IPv4[^\d]*(\d+\.\d+\.\d+\.\d+)', section)
                    mask_match = re.search(r'M.scara de subred[^\d]*(\d+\.\d+\.\d+\.\d+)', section)
                    
                    if ip_match and mask_match:
                        ip = ip_match.group(1)
                        mask_str = mask_match.group(1)
                        
                        # Calcular dirección de broadcast
                        try:
                            ip_parts = list(map(int, ip.split(".")))
                            mask_parts = list(map(int, mask_str.split(".")))
                            broadcast_parts = []
                            
                            for i in range(4):
                                broadcast_parts.append(ip_parts[i] | (~mask_parts[i] & 0xFF))
                            
                            broadcast = ".".join(map(str, broadcast_parts))
                            if broadcast not in broadcast_addresses:
                                broadcast_addresses.append(broadcast)
                        except (ValueError, IndexError):
                            continue
                            
        except subprocess.CalledProcessError:
            pass
    
    return broadcast_addresses

class LCPeer:
    def __init__(self, nombre_usuario: str):
        # Constantes del protocolo
        self.PUERTO_UDP = 9990
        self.PUERTO_TCP = 9990
        self.TAMANO_ENCABEZADO = 100
        self.TAMANO_RESPUESTA = 25
        self.DIRECCION_DIFUSION = get_info()
        print(self.DIRECCION_DIFUSION)
        # Códigos de operación
        self.OPERACION_ECO = 0
        self.OPERACION_MENSAJE = 1
        self.OPERACION_ARCHIVO = 2
        
        # Códigos de estado de respuesta
        self.ESTADO_OK = 0
        self.ESTADO_PETICION_INVALIDA = 1
        self.ESTADO_ERROR_INTERNO = 2

        self.id_usuario = nombre_usuario.ljust(20)[:20].encode('utf-8')  # 20 bytes fijos
        self.pares_conocidos: Dict[str, str] = {}  # id_par -> direccion_par
        self.cola_mensajes: List[tuple] = []  # (id_remitente, mensaje)
        self.activo = False
        
        # Crear socket UDP para mensajes de control
        self.socket_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket_udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.socket_udp.bind(('', self.PUERTO_UDP))
        
        # Crear socket TCP para transferencias de archivos
        self.socket_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket_tcp.bind(('', self.PUERTO_TCP))
        self.socket_tcp.listen(5)


        
    def iniciar(self):
        """Inicia los hilos principales del par"""
        self.activo = True
        
        # Iniciar hilos de escucha
        threading.Thread(target=self._escuchar_udp, daemon=True).start()
        threading.Thread(target=self._escuchar_tcp, daemon=True).start()
        
        # Iniciar hilo de descubrimiento
        threading.Thread(target=self._bucle_descubrimiento, daemon=True).start()
        
    def detener(self):
        """Detiene el par y libera recursos"""
        self.activo = False
        self.socket_udp.close()
        self.socket_tcp.close()
        
    def _escuchar_udp(self):
        """Escucha mensajes UDP"""
        while self.activo:
            try:
                datos, direccion = self.socket_udp.recvfrom(1024)
                self._manejar_mensaje_udp(datos, direccion)
            except Exception as e:
                print(f"Error en el escuchador UDP: {e}")
                
    def _escuchar_tcp(self):
        """Escucha conexiones TCP (transferencias de archivos)"""
        while self.activo:
            try:
                conexion, direccion = self.socket_tcp.accept()
                threading.Thread(target=self._manejar_conexion_tcp, args=(conexion, direccion)).start()
            except Exception as e:
                print(f"Error en el escuchador TCP: {e}")
                
    def _bucle_descubrimiento(self):
        """Difunde periódicamente mensajes de descubrimiento"""
        while self.activo:
            self._enviar_eco()
            time.sleep(5)  # Enviar descubrimiento cada 5 segundos
            
    def _enviar_eco(self):
        """Envía mensaje de descubrimiento"""
        encabezado = self._crear_encabezado(self.OPERACION_ECO, b'\xFF' * 20)
        for i in self.DIRECCION_DIFUSION:
            print(i)
            self.socket_udp.sendto(encabezado, (i, self.PUERTO_UDP))
        
    def _crear_encabezado(self, operacion: int, id_usuario_destino: bytes) -> bytes:
        """Crea un encabezado de protocolo"""
        encabezado = bytearray(self.TAMANO_ENCABEZADO)  # Debería ser 100 bytes
    
        # UserIdFrom (20 bytes)
        encabezado[0:20] = self.id_usuario.ljust(20, b'\x00')[:20]
        
        # UserIdTo (20 bytes)
        encabezado[20:40] = id_usuario_destino.ljust(20, b'\x00')[:20]
        
        # OperationCode (1 byte)
        encabezado[40] = operacion
        
        # BodyId (1 byte, inicializado a 0)
        encabezado[41] = 0
        
        # BodyLength (8 bytes, inicializado a 0)
        encabezado[42:50] = b'\x00\x00\x00\x00\x00\x00\x00\x00'
        
        # Reserved (50 bytes)
        encabezado[50:100] = b'\x00' * 50
        
        return bytes(encabezado)
    def _manejar_mensaje_udp(self, datos: bytes, direccion: tuple):
        """Maneja mensajes UDP entrantes"""
        if len(datos) < self.TAMANO_ENCABEZADO:
            return
            
        id_usuario_remitente = datos[0:20]
        id_usuario_destino = datos[20:40]
        operacion = datos[40]
        
        if operacion == self.OPERACION_ECO:
            self._manejar_eco(id_usuario_remitente, direccion)
        elif operacion == self.OPERACION_MENSAJE:
            self._manejar_mensaje(id_usuario_remitente, datos)
            
    def _manejar_eco(self, id_usuario_remitente: bytes, direccion: tuple):
        """Maneja mensajes de descubrimiento"""
        if id_usuario_remitente != self.id_usuario:  # No responder a uno mismo
            self.pares_conocidos[id_usuario_remitente.decode('utf-8').strip()] = direccion[0]
            print(id_usuario_remitente)
            print(direccion)
            # Enviar respuesta
            respuesta = bytes([self.ESTADO_OK]) + self.id_usuario + b'\x00'*4
            self.socket_udp.sendto(respuesta, direccion)
            
    def _manejar_mensaje(self, id_usuario_remitente: bytes, datos: bytes):
        """Maneja mensajes entrantes"""
        operacion = datos[40]
        
        if operacion == self.OPERACION_ECO:
            self._manejar_eco(id_usuario_remitente, datos)
        elif operacion == self.OPERACION_MENSAJE:
            self._manejar_mensaje(id_usuario_remitente, datos)
        elif operacion == self.OPERACION_ARCHIVO:
            self._manejar_archivo(id_usuario_remitente, datos)  # Implementar si es necesario
        
    def enviar_mensaje(self, destinatario: str, mensaje: str):
        """Envía un mensaje a un par específico"""
        if destinatario not in self.pares_conocidos:
            print(f"Destinatario {destinatario} no encontrado")
            return
            
        # TODO: Implementar envío de mensajes
        pass
        
    def enviar_archivo(self, destinatario: str, ruta_archivo: str):
        """Envía un archivo a un par específico"""
        if destinatario not in self.pares_conocidos:
            print(f"Destinatario {destinatario} no encontrado")
            return
            
        # TODO: Implementar transferencia de archivos
        pass
