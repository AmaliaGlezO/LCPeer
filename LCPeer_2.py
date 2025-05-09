import socket
import threading
import time
from typing import Dict, List, Optional, Tuple
import subprocess
import platform
import re
import os
import struct

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
        self.TIMEOUT_RESPUESTA = 5  # segundos
        self.DIRECCION_DIFUSION = get_info()
        print(f"Direcciones de difusión obtenidas: {self.DIRECCION_DIFUSION}")
        
        # Códigos de operación
        self.OPERACION_ECO = 0
        self.OPERACION_MENSAJE = 1
        self.OPERACION_ARCHIVO = 2
        
        # Códigos de estado de respuesta
        self.ESTADO_OK = 0
        self.ESTADO_PETICION_INVALIDA = 1
        self.ESTADO_ERROR_INTERNO = 2

        # Validar y formatear el ID de usuario
        if len(nombre_usuario) > 20 or len(nombre_usuario) == 0:
            raise ValueError("El nombre de usuario debe tener entre 1 y 20 caracteres")
        self.id_usuario = nombre_usuario.ljust(20)[:20].encode('utf-8')
        
        # Estructuras de datos
        self.pares_conocidos: Dict[str, Tuple[str, int]] = {}  # id_par -> (ip, puerto)
        self.cola_mensajes: List[Tuple[str, str]] = []  # (id_remitente, mensaje)
        self.archivos_pendientes: Dict[int, Tuple[str, str, int]] = {}  # body_id -> (remitente, nombre_archivo, tamaño)
        self.activo = False
        self.contador_body_id = 0
        
        # Configurar sockets
        self._configurar_sockets()

    def _configurar_sockets(self):
        """Configura los sockets UDP y TCP"""
        # Socket UDP para mensajes de control
        self.socket_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket_udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.socket_udp.bind(('', self.PUERTO_UDP))
        print(f"Socket UDP creado y vinculado al puerto {self.PUERTO_UDP}")
        
        # Socket TCP para transferencias de archivos
        self.socket_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket_tcp.bind(('', self.PUERTO_TCP))
        self.socket_tcp.listen(5)
        print(f"Socket TCP creado y escuchando en el puerto {self.PUERTO_TCP}")

    def iniciar(self):
        """Inicia los hilos principales del par"""
        if self.activo:
            print("El peer ya está activo.")
            return
            
        self.activo = True
        print("Iniciando el peer...")
        
        # Hilos de escucha
        threading.Thread(target=self._escuchar_udp, daemon=True).start()
        threading.Thread(target=self._escuchar_tcp, daemon=True).start()
        
        # Hilo de descubrimiento
        threading.Thread(target=self._bucle_descubrimiento, daemon=True).start()
        
        print(f"Peer {self.id_usuario.decode('utf-8').strip()} iniciado correctamente")

    def detener(self):
        """Detiene el par y libera recursos"""
        if not self.activo:
            print("El peer ya está detenido.")
            return
            
        self.activo = False
        self.socket_udp.close()
        self.socket_tcp.close()
        print("Peer detenido correctamente")

    def _escuchar_udp(self):
        """Escucha mensajes UDP"""
        print("Escuchando mensajes UDP...")
        while self.activo:
            try:
                datos, direccion = self.socket_udp.recvfrom(1024)
                print(f"Datos recibidos de {direccion}: {datos}")
                self._procesar_encabezado_udp(datos, direccion)
            except Exception as e:
                print(f"Error en el escuchador UDP: {e}")

    def _escuchar_tcp(self):
        """Escucha conexiones TCP para transferencias de archivos"""
        print("Escuchando conexiones TCP...")
        while self.activo:
            try:
                conexion, direccion = self.socket_tcp.accept()
                print(f"Conexión TCP aceptada de {direccion}")
                threading.Thread(target=self._manejar_conexion_tcp, args=(conexion, direccion)).start()
            except Exception as e:
                print(f"Error en el escuchador TCP: {e}")

    def _bucle_descubrimiento(self):
        """Difunde periódicamente mensajes de descubrimiento"""
        print("Iniciando bucle de descubrimiento...")
        while self.activo:
            self._enviar_eco()
            time.sleep(5)

    def _enviar_eco(self):
        """Envía mensaje de descubrimiento (broadcast)"""
        print("Enviando eco...")
        encabezado = self._crear_encabezado(self.OPERACION_ECO, b'\xFF'*20)
        for ip in self.DIRECCION_DIFUSION:
            self.socket_udp.sendto(encabezado, (ip, self.PUERTO_UDP))
            print(f"Eco enviado a: {ip}:{self.PUERTO_UDP}")

    def _crear_encabezado(self, operacion: int, id_destino: bytes, body_id: int = 0, body_length: int = 0) -> bytes:
        """Crea un encabezado de protocolo de 100 bytes exactos"""
        encabezado = bytearray(self.TAMANO_ENCABEZADO)
        
        # UserIdFrom (20 bytes)
        encabezado[0:20] = self.id_usuario
        
        # UserIdTo (20 bytes) - Asegúrate de que id_destino sea un byte string
        encabezado[20:40] = id_destino.ljust(20, b'\x00')[:20]  # Cambiado a b'\x00'
        
        # OperationCode (1 byte)
        encabezado[40] = operacion
        
        # BodyId (1 byte)
        encabezado[41] = body_id
        
        # BodyLength (8 bytes, big-endian)
        encabezado[42:50] = body_length.to_bytes(8, byteorder='big')
        
        # Reserved (50 bytes)
        encabezado[50:100] = b'\x00' * 50
        
        return bytes(encabezado)

    def _crear_respuesta(self, estado: int) -> bytes:
        """Crea una respuesta de protocolo de 25 bytes exactos"""
        respuesta = bytearray(self.TAMANO_RESPUESTA)
        
        # ResponseStatus (1 byte)
        respuesta[0] = estado
        
        # ResponseId (20 bytes)
        respuesta[1:21] = self.id_usuario
        
        # Reserved (4 bytes)
        respuesta[21:25] = b'\x00' * 4
        
        return bytes(respuesta)

    def _procesar_encabezado_udp(self, datos: bytes, direccion: tuple):
        """Procesa un encabezado UDP recibido"""
        print(f"Manejando encabezado UDP de {direccion}")
        try:
            id_remitente = datos[0:20]
            id_destino = datos[20:40]
            operacion = datos[40]
            body_id = datos[41]
            body_length = int.from_bytes(datos[42:50], byteorder='big')
            
            print(f"ID Remitente: {id_remitente.decode('utf-8').strip()}, ID Destino: {id_destino.decode('utf-8').strip()}, Operación: {operacion}")
            
            # Verificar si el mensaje es para nosotros o es broadcast
            if id_destino != b'\xFF'*20 and id_destino != self.id_usuario:
                return
                
            id_remitente_str = id_remitente.decode('utf-8').strip()
            ip_remitente, puerto_remitente = direccion
            
            # Actualizar lista de pares conocidos
            if id_remitente_str and id_remitente_str != self.id_usuario.decode('utf-8').strip():
                self.pares_conocidos[id_remitente_str] = (ip_remitente, puerto_remitente)
                print(f"Par conocido agregado: {id_remitente_str} -> {direccion}")
            
            # Manejar según operación
            if operacion == self.OPERACION_ECO:
                self._manejar_eco(id_remitente, (ip_remitente, puerto_remitente))
            elif operacion == self.OPERACION_MENSAJE:
                self._manejar_mensaje(id_remitente, body_id, body_length, (ip_remitente, puerto_remitente))
            elif operacion == self.OPERACION_ARCHIVO:
                self._manejar_solicitud_archivo(id_remitente, body_id, body_length, (ip_remitente, puerto_remitente))
                
        except Exception as e:
            print(f"Error al procesar encabezado UDP: {e}")

    def _manejar_eco(self, id_remitente: bytes, direccion: tuple):
        """Maneja mensajes de descubrimiento (eco)"""
        print(f"Manejando eco de {id_remitente.decode('utf-8').strip()} desde {direccion}")
        try:
            # Enviar respuesta de eco
            respuesta = self._crear_respuesta(self.ESTADO_OK)
            self.socket_udp.sendto(respuesta, direccion)
            print(f"Respuesta de eco enviada a {direccion}")
        except Exception as e:
            print(f"Error al manejar eco: {e}")

    def _manejar_mensaje(self, id_remitente: bytes, body_id: int, body_length: int, direccion: tuple):
        """Maneja mensajes de texto"""
        print(f"Manejando mensaje de {id_remitente.decode('utf-8').strip()}")
        try:
            # Enviar confirmación de recepción del encabezado
            respuesta = self._crear_respuesta(self.ESTADO_OK)
            self.socket_udp.sendto(respuesta, direccion)
            
            # Esperar el cuerpo del mensaje
            self.socket_udp.settimeout(self.TIMEOUT_RESPUESTA)
            datos, _ = self.socket_udp.recvfrom(body_length + 8  ) # +8 por el body_id
            
            # Verificar que el body_id coincida
            recibido_body_id = datos[0]
            if recibido_body_id != body_id:
                raise ValueError("Body ID no coincide")
                
            mensaje = datos[8:].decode('utf-8')
            id_remitente_str = id_remitente.decode('utf-8').strip()
            
            # Agregar a la cola de mensajes
            self.cola_mensajes.append((id_remitente_str, mensaje))
            print(f"\n[Nuevo mensaje de {id_remitente_str}]: {mensaje}")
            
        except socket.timeout:
            print("Tiempo de espera agotado para recibir mensaje")
        except Exception as e:
            print(f"Error al manejar mensaje: {e}")
        finally:
            self.socket_udp.settimeout(1)

    def _manejar_solicitud_archivo(self, id_remitente: bytes, body_id: int, body_length: int, direccion: tuple):
        """Maneja solicitudes de transferencia de archivos"""
        print(f"Manejando solicitud de archivo de {id_remitente.decode('utf-8').strip()} a {direccion}")
        try:
            # Enviar confirmación de recepción del encabezado
            respuesta = self._crear_respuesta(self.ESTADO_OK)
            self.socket_udp.sendto(respuesta, direccion)
            
            # Esperar conexión TCP para recibir el archivo
            self.archivos_pendientes[body_id] = (
                id_remitente.decode('utf-8').strip(),
                f"archivo_recibido_{body_id}",
                body_length
            )
            print(f"\nPreparado para recibir archivo (ID: {body_id}) de {id_remitente.decode('utf-8').strip()}...")
            
        except Exception as e:
            print(f"Error al manejar solicitud de archivo: {e}")

    def _manejar_conexion_tcp(self, conexion: socket.socket, direccion: tuple):
        """Maneja una conexión TCP entrante para transferencia de archivos"""
        print(f"Manejando conexión TCP de {direccion}")
        try:
            # Recibir los primeros 8 bytes (body_id)
            datos = conexion.recv(8)
            if len(datos) != 8:
                raise ValueError("Encabezado de archivo incompleto")
                
            body_id = datos[0]
            
            # Verificar si esperábamos este archivo
            if body_id not in self.archivos_pendientes:
                raise ValueError("Body ID de archivo no reconocido")
                
            remitente, nombre_archivo, tamaño = self.archivos_pendientes[body_id]
            del self.archivos_pendientes[body_id]
            
            # Recibir el archivo
            with open(nombre_archivo, 'wb') as f:
                recibido = 0
                while recibido < tamaño:
                    datos = conexion.recv(min(4096, tamaño - recibido))
                    if not datos:
                        break
                    f.write(datos)
                    recibido += len(datos)
                
            # Enviar confirmación
            respuesta = self._crear_respuesta(self.ESTADO_OK if recibido == tamaño else self.ESTADO_ERROR_INTERNO)
            conexion.sendall(respuesta)
            
            print(f"\n[Archivo recibido de {remitente}]: {nombre_archivo} ({recibido} bytes)")
            
        except Exception as e:
            print(f"Error al manejar conexión TCP: {e}")
        finally:
            conexion.close()

    def enviar_mensaje(self, destinatario: str, mensaje: str):
        """Envía un mensaje de texto a otro peer"""
        if destinatario not in self.pares_conocidos:
            print(f"Destinatario {destinatario} no encontrado")
            return False
            
        print(f"Enviando mensaje a {destinatario}: {mensaje}")
        try:
            ip, puerto = self.pares_conocidos[destinatario]
            id_destino = destinatario.ljust(20)[:20].encode('utf-8')
            
            # Generar body_id único
            self.contador_body_id = (self.contador_body_id + 1) % 256
            body_id = self.contador_body_id
            
            # Crear y enviar encabezado
            mensaje_bytes = mensaje.encode('utf-8')
            encabezado = self._crear_encabezado(
                self.OPERACION_MENSAJE,
                id_destino,
                body_id,
                len(mensaje_bytes)
            )
            self.socket_udp.sendto(encabezado, (ip, puerto))
            print(f"Encabezado enviado a {destinatario}")
            
            # Esperar confirmación
            self.socket_udp.settimeout(self.TIMEOUT_RESPUESTA)
            respuesta, _ = self.socket_udp.recvfrom(self.TAMANO_RESPUESTA)
            
            if respuesta[0] != self.ESTADO_OK:
                print("Error en la confirmación del mensaje")
                return False
                
            # Enviar cuerpo del mensaje
            cuerpo = bytes([body_id]) + b'\x00'*7 + mensaje_bytes
            self.socket_udp.sendto(cuerpo, (ip, puerto))
            print(f"Cuerpo del mensaje enviado a {destinatario}")
            
            # Esperar confirmación final
            respuesta, _ = self.socket_udp.recvfrom(self.TAMANO_RESPUESTA)
            if respuesta[0] == self.ESTADO_OK:
                print(f"Mensaje enviado correctamente a {destinatario}")
                return True
            else:
                print("Error al confirmar recepción del mensaje")
                return False
                
        except socket.timeout:
            print("Tiempo de espera agotado al enviar mensaje")
            return False
        except Exception as e:
            print(f"Error al enviar mensaje: {e}")
            return False
        finally:
            self.socket_udp.settimeout(1)

    def enviar_archivo(self, destinatario: str, ruta_archivo: str):
        """Envía un archivo a otro peer"""
        if destinatario not in self.pares_conocidos:
            print(f"Destinatario {destinatario} no encontrado")
            return False
            
        if not os.path.isfile(ruta_archivo):
            print(f"Archivo {ruta_archivo} no encontrado")
            return False
            
        try:
            ip, puerto = self.pares_conocidos[destinatario]
            id_destino = destinatario.ljust(20)[:20].encode('utf-8')
            nombre_archivo = os.path.basename(ruta_archivo)
            tamaño_archivo = os.path.getsize(ruta_archivo)
            
            # Generar body_id único
            self.contador_body_id = (self.contador_body_id + 1) % 256
            body_id = self.contador_body_id
            
            # Enviar encabezado por UDP
            encabezado = self._crear_encabezado(
                self.OPERACION_ARCHIVO,
                id_destino,
                body_id,
                tamaño_archivo
            )
            self.socket_udp.sendto(encabezado, (ip, puerto))
            print(f"Encabezado de archivo enviado a {destinatario}")
            
            # Esperar confirmación
            self.socket_udp.settimeout(self.TIMEOUT_RESPUESTA)
            respuesta, _ = self.socket_udp.recvfrom(self.TAMANO_RESPUESTA)
            
            if respuesta[0] != self.ESTADO_OK:
                print("El destinatario rechazó la transferencia de archivo")
                return False
                
            # Establecer conexión TCP
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((ip, self.PUERTO_TCP))
                
                # Enviar body_id (8 bytes)
                s.sendall(bytes([body_id]) + b'\x00'*7)
                print(f"Body ID enviado a {destinatario}")
                
                # Enviar archivo
                with open(ruta_archivo, 'rb') as f:
                    while True:
                        datos = f.read(4096)
                        if not datos:
                            break
                        s.sendall(datos)
                
                # Esperar confirmación final
                respuesta = s.recv(self.TAMANO_RESPUESTA)
                if len(respuesta) >= 1 and respuesta[0] == self.ESTADO_OK:
                    print(f"Archivo {nombre_archivo} enviado correctamente a {destinatario}")
                    return True
                else:
                    print("Error al confirmar recepción del archivo")
                    return False
                    
        except socket.timeout:
            print("Tiempo de espera agotado al enviar archivo")
            return False
        except Exception as e:
            print(f"Error al enviar archivo: {e}")
            return False
        finally:
            self.socket_udp.settimeout(1)

def get_broadcast_addresses():
    """Obtiene direcciones de broadcast para la red local"""
    broadcast_addresses = []
    system = platform.system()
    
    if system == "Windows":
        try:
            output = subprocess.check_output(["ipconfig"], universal_newlines=True, encoding='cp437')
            sections = output.split("\n\n")
            
            for section in sections:
                if "Direcci" in section and ("IPv4" in section or "IP4" in section):
                    ip_match = re.search(r'Direcci.n IPv4[^\d]*(\d+\.\d+\.\d+\.\d+)', section)
                    mask_match = re.search(r'M.scara de subred[^\d]*(\d+\.\d+\.\d+\.\d+)', section)
                    
                    if ip_match and mask_match:
                        ip = ip_match.group(1)
                        mask_str = mask_match.group(1)
                        
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
    
    return broadcast_addresses or ['<broadcast>']