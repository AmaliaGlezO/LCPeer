from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QListWidget, QTextEdit, QLineEdit, 
                            QPushButton, QTabWidget, QLabel, QFileDialog,
                            QMessageBox, QSplitter, QInputDialog)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
import sys
from LCPeer import LCPeer
import time

class WorkerThread(QThread):
    actualizar_usuarios = pyqtSignal(list)
    nuevo_mensaje = pyqtSignal(str, str)  # remitente, mensaje
    
    def __init__(self, peer):
        super().__init__()
        self.peer = peer
        self.activo = True
        
    def run(self):
        while self.activo:
            # Actualizar lista de usuarios
            usuarios = list(self.peer.pares_conocidos.keys())
            self.actualizar_usuarios.emit(usuarios)
            
            # Verificar mensajes nuevos
            while self.peer.cola_mensajes:
                remitente, mensaje = self.peer.cola_mensajes.pop(0)
                self.nuevo_mensaje.emit(remitente, mensaje)
                
            time.sleep(0.1)  # Pequeña pausa para no sobrecargar la CPU
            
    def detener(self):
        self.activo = False

class ChatWidget(QWidget):
    def __init__(self, nombre_usuario, peer):
        super().__init__()
        self.nombre_usuario = nombre_usuario
        self.peer = peer
        self.initUI()
        
    def initUI(self):
        # Layout principal
        layout = QVBoxLayout()
        
        # Splitter para dividir la ventana
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Panel izquierdo (usuarios)
        panel_usuarios = QWidget()
        layout_usuarios = QVBoxLayout()
        
        # Título de usuarios
        titulo_usuarios = QLabel("Usuarios Conectados")
        titulo_usuarios.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout_usuarios.addWidget(titulo_usuarios)
        
        # Lista de usuarios
        self.lista_usuarios = QListWidget()
        self.lista_usuarios.setFont(QFont("Arial", 10))
        layout_usuarios.addWidget(self.lista_usuarios)
        
        panel_usuarios.setLayout(layout_usuarios)
        
        # Panel derecho (chat)
        panel_chat = QWidget()
        layout_chat = QVBoxLayout()
        
        # Área de chat
        self.area_chat = QTextEdit()
        self.area_chat.setReadOnly(True)
        self.area_chat.setFont(QFont("Arial", 10))
        layout_chat.addWidget(self.area_chat)
        
        # Panel de entrada
        panel_entrada = QWidget()
        layout_entrada = QHBoxLayout()
        
        self.entrada_mensaje = QLineEdit()
        self.entrada_mensaje.setPlaceholderText("Escribe tu mensaje...")
        self.entrada_mensaje.returnPressed.connect(self.enviar_mensaje)
        
        btn_enviar = QPushButton("Enviar")
        btn_enviar.clicked.connect(self.enviar_mensaje)
        
        btn_archivo = QPushButton("Archivo")
        btn_archivo.clicked.connect(self.enviar_archivo)
        
        layout_entrada.addWidget(self.entrada_mensaje)
        layout_entrada.addWidget(btn_enviar)
        layout_entrada.addWidget(btn_archivo)
        
        panel_entrada.setLayout(layout_entrada)
        layout_chat.addWidget(panel_entrada)
        
        panel_chat.setLayout(layout_chat)
        
        # Agregar paneles al splitter
        splitter.addWidget(panel_usuarios)
        splitter.addWidget(panel_chat)
        splitter.setSizes([200, 600])  # Tamaños iniciales
        
        layout.addWidget(splitter)
        self.setLayout(layout)
        
    def enviar_mensaje(self):
        seleccion = self.lista_usuarios.selectedItems()
        if not seleccion:
            QMessageBox.warning(self, "Advertencia", "Selecciona un destinatario")
            return
            
        destinatario = seleccion[0].text()
        mensaje = self.entrada_mensaje.text()
        
        if mensaje:
            self.peer.enviar_mensaje(destinatario, mensaje)
            self.mostrar_mensaje(self.nombre_usuario, mensaje)
            self.entrada_mensaje.clear()
            
    def enviar_archivo(self):
        seleccion = self.lista_usuarios.selectedItems()
        if not seleccion:
            QMessageBox.warning(self, "Advertencia", "Selecciona un destinatario")
            return
            
        destinatario = seleccion[0].text()
        ruta_archivo, _ = QFileDialog.getOpenFileName(self, "Seleccionar archivo")
        
        if ruta_archivo:
            self.peer.enviar_archivo(destinatario, ruta_archivo)
            self.mostrar_mensaje("Sistema", f"Enviando archivo: {ruta_archivo}")
            
    def mostrar_mensaje(self, remitente, mensaje):
        self.area_chat.append(f"<b>{remitente}:</b> {mensaje}")
        
    def actualizar_lista_usuarios(self, usuarios):
        self.lista_usuarios.clear()
        for usuario in usuarios:
            self.lista_usuarios.addItem(usuario)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle("Chat LAN")
        self.setGeometry(100, 100, 1000, 600)
        
        # Widget central con pestañas
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Pedir nombre de usuario
        nombre, ok = QInputDialog.getText(self, "Nombre de usuario", 
                                        "Ingresa tu nombre de usuario:")
        if not ok or not nombre:
            sys.exit()
            
        # Inicializar peer
        self.peer = LCPeer(nombre)
        self.peer.iniciar()
        
        # Crear widget de chat principal
        self.chat_principal = ChatWidget(nombre, self.peer)
        self.tabs.addTab(self.chat_principal, "Chat Principal")
        
        # Iniciar hilo de trabajo
        self.worker = WorkerThread(self.peer)
        self.worker.actualizar_usuarios.connect(self.chat_principal.actualizar_lista_usuarios)
        self.worker.nuevo_mensaje.connect(self.chat_principal.mostrar_mensaje)
        self.worker.start()
        
    def closeEvent(self, event):
        self.worker.detener()
        self.peer.detener()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Estilo moderno
    
    # Establecer tema oscuro
    palette = app.palette()
    palette.setColor(palette.ColorRole.Window, Qt.GlobalColor.darkGray)
    palette.setColor(palette.ColorRole.WindowText, Qt.GlobalColor.white)
    palette.setColor(palette.ColorRole.Base, Qt.GlobalColor.darkGray)
    palette.setColor(palette.ColorRole.AlternateBase, Qt.GlobalColor.darkGray)
    palette.setColor(palette.ColorRole.ToolTipBase, Qt.GlobalColor.darkGray)
    palette.setColor(palette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    palette.setColor(palette.ColorRole.Text, Qt.GlobalColor.white)
    palette.setColor(palette.ColorRole.Button, Qt.GlobalColor.darkGray)
    palette.setColor(palette.ColorRole.ButtonText, Qt.GlobalColor.white)
    palette.setColor(palette.ColorRole.BrightText, Qt.GlobalColor.red)
    palette.setColor(palette.ColorRole.Link, Qt.GlobalColor.cyan)
    palette.setColor(palette.ColorRole.Highlight, Qt.GlobalColor.cyan)
    palette.setColor(palette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    app.setPalette(palette)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec()) 