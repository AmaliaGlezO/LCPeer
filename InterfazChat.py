import tkinter as tk
from tkinter import scrolledtext, filedialog
from LCPeer import LCPeer
import threading
import time

class InterfazChat:
    def __init__(self):
        # Crear ventana principal
        self.ventana = tk.Tk()
        self.ventana.title("Chat LAN")
        self.ventana.geometry("800x600")
        
        # Pedir nombre de usuario
        self.nombre_usuario = self._pedir_nombre_usuario()
        if not self.nombre_usuario.strip():  # Si el nombre está vacío, salir
            self.ventana.destroy()
            return
        
        # Inicializar el peer
        self.peer = LCPeer(self.nombre_usuario)
        
        # Crear interfaz
        self._crear_interfaz()
        
        # Iniciar el peer en un hilo separado
        self.hilo_peer = threading.Thread(target=self._iniciar_peer, daemon=True)
        self.hilo_peer.start()
        
    def _pedir_nombre_usuario(self):
        # Ventana para ingresar nombre
        ventana_nombre = tk.Toplevel(self.ventana)
        ventana_nombre.title("Ingresa tu nombre")
        ventana_nombre.geometry("300x150")
        
        nombre = tk.StringVar()
        
        tk.Label(ventana_nombre, text="Nombre de usuario:").pack(pady=10)
        entrada = tk.Entry(ventana_nombre, textvariable=nombre)
        entrada.pack(pady=5)
        entrada.focus_set()  # Poner el foco en el Entry
        
        # Frame para botones
        frame_botones = tk.Frame(ventana_nombre)
        frame_botones.pack(pady=5)
        
        # Botón Aceptar
        btn_aceptar = tk.Button(frame_botones, text="Aceptar", 
                               command=lambda: ventana_nombre.destroy() if nombre.get().strip() else None)
        btn_aceptar.pack(side=tk.LEFT, padx=5)
        
        # Vincular la tecla Enter al botón Aceptar
        entrada.bind("<Return>", lambda e: ventana_nombre.destroy() if nombre.get().strip() else None)
        
        # Hacer la ventana modal
        ventana_nombre.grab_set()
        ventana_nombre.transient(self.ventana)
        ventana_nombre.protocol("WM_DELETE_WINDOW", lambda: None)  # Deshabilitar cierre con X
        ventana_nombre.wait_window()
        
        return nombre.get()
        
    def _crear_interfaz(self):
        # Frame principal
        frame_principal = tk.Frame(self.ventana)
        frame_principal.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Frame para lista de usuarios
        frame_usuarios = tk.LabelFrame(frame_principal, text="Usuarios Conectados")
        frame_usuarios.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # Lista de usuarios
        self.lista_usuarios = tk.Listbox(frame_usuarios, width=20)
        self.lista_usuarios.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Frame para chat
        frame_chat = tk.Frame(frame_principal)
        frame_chat.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Área de chat
        self.area_chat = scrolledtext.ScrolledText(frame_chat, wrap=tk.WORD)
        self.area_chat.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.area_chat.config(state=tk.DISABLED)
        
        # Frame para entrada de mensaje
        frame_entrada = tk.Frame(frame_chat)
        frame_entrada.pack(fill=tk.X, padx=5, pady=5)
        
        # Campo de entrada
        self.entrada_mensaje = tk.Entry(frame_entrada)
        self.entrada_mensaje.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entrada_mensaje.bind("<Return>", self._enviar_mensaje)
        
        # Botones
        tk.Button(frame_entrada, text="Enviar", command=self._enviar_mensaje).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_entrada, text="Archivo", command=self._enviar_archivo).pack(side=tk.LEFT, padx=5)
        
    def _iniciar_peer(self):
        self.peer.iniciar()
        # Actualizar lista de usuarios periódicamente
        while True:
            self._actualizar_usuarios()
            time.sleep(1)
            
    def _actualizar_usuarios(self):
        # Limpiar lista actual
        self.lista_usuarios.delete(0, tk.END)
        # Agregar usuarios conocidos
        for usuario in self.peer.pares_conocidos:
            self.lista_usuarios.insert(tk.END, usuario)
            
    def _enviar_mensaje(self, event=None):
        # Obtener destinatario seleccionado
        seleccion = self.lista_usuarios.curselection()
        if not seleccion:
            self._mostrar_mensaje("Sistema", "Selecciona un destinatario")
            return
            
        destinatario = self.lista_usuarios.get(seleccion[0])
        mensaje = self.entrada_mensaje.get()
        
        if mensaje:
            # Enviar mensaje
            self.peer.enviar_mensaje(destinatario, mensaje)
            # Mostrar en el chat
            self._mostrar_mensaje(self.nombre_usuario, mensaje)
            # Limpiar entrada
            self.entrada_mensaje.delete(0, tk.END)
            
    def _enviar_archivo(self):
        # Obtener destinatario seleccionado
        seleccion = self.lista_usuarios.curselection()
        if not seleccion:
            self._mostrar_mensaje("Sistema", "Selecciona un destinatario")
            return
            
        destinatario = self.lista_usuarios.get(seleccion[0])
        
        # Abrir diálogo para seleccionar archivo
        ruta_archivo = filedialog.askopenfilename()
        if ruta_archivo:
            # Enviar archivo
            self.peer.enviar_archivo(destinatario, ruta_archivo)
            self._mostrar_mensaje("Sistema", f"Enviando archivo: {ruta_archivo}")
            
    def _mostrar_mensaje(self, remitente, mensaje):
        self.area_chat.config(state=tk.NORMAL)
        self.area_chat.insert(tk.END, f"{remitente}: {mensaje}\n")
        self.area_chat.config(state=tk.DISABLED)
        self.area_chat.see(tk.END)
        
    def iniciar(self):
        self.ventana.mainloop()
        
if __name__ == "__main__":
    app = InterfazChat()
    app.iniciar()