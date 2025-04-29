import socket
import threading
import time
from typing import Dict, List, Optional

class LCPeer:
    # Constantes del protocolo
    PUERTO_UDP = 9990
    PUERTO_TCP = 9990
    TAMANO_ENCABEZADO = 100
    TAMANO_RESPUESTA = 25
    DIRECCION_DIFUSION = "255.255.255.255"
    
    # Códigos de operación
    OPERACION_ECO = 0
    OPERACION_MENSAJE = 1
    OPERACION_ARCHIVO = 2
    
    # Códigos de estado de respuesta
    ESTADO_OK = 0
    ESTADO_PETICION_INVALIDA = 1
    ESTADO_ERROR_INTERNO = 2
    
    def __init__(self, nombre_usuario: str):
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
                datos, direccion = self.socket_udp.recvfrom(self.TAMANO_ENCABEZADO)
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
        self.socket_udp.sendto(encabezado, (self.DIRECCION_DIFUSION, self.PUERTO_UDP))
        
    def _crear_encabezado(self, operacion: int, id_usuario_destino: bytes) -> bytes:
        """Crea un encabezado de protocolo"""
        encabezado = bytearray(self.TAMANO_ENCABEZADO)
        encabezado[0:20] = self.id_usuario  # IdUsuarioRemitente
        encabezado[20:40] = id_usuario_destino   # IdUsuarioDestino
        encabezado[40] = operacion       # CodigoOperacion
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
            # Enviar respuesta
            respuesta = bytes([self.ESTADO_OK]) + self.id_usuario
            self.socket_udp.sendto(respuesta, direccion)
            
    def _manejar_mensaje(self, id_usuario_remitente: bytes, datos: bytes):
        """Maneja mensajes entrantes"""
        # TODO: Implementar manejo de mensajes
        pass
        
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
