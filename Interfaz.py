import customtkinter as ctk
from tkinter import filedialog, messagebox
from threading import Thread
from LCPeer_Pruebas import LCPClient
import time

class LCPGUI:
    def __init__(self, root):
        ctk.set_appearance_mode("light")  # Puedes cambiar a "dark" si prefieres
        ctk.set_default_color_theme("blue")  # Otros temas: "green", "dark-blue"
        self.root = root
        self.root.title("LCPeer Chat")
        self.root.geometry("900x600")
        self.root.minsize(800, 500)  # Tamaño mínimo
        
        self.client = None
        self.active_peer = None
        self.unread_counts = {}
        self.global_chat_active = True

        self._build_login()

    def _build_login(self):
        self.login_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.login_frame.pack(expand=True, fill="both", padx=50, pady=50)
        
        # Logo o título
        ctk.CTkLabel(self.login_frame, 
                    text="LCPeer Chat", 
                    font=("Arial", 24, "bold")).pack(pady=(0, 30))
        
        # Frame para los elementos de login
        login_form = ctk.CTkFrame(self.login_frame, fg_color="transparent")
        login_form.pack()
        
        ctk.CTkLabel(login_form, 
                    text="Ingresa tu ID (max 20 caracteres):",
                    font=("Arial", 12)).pack(pady=(0, 5))
        
        self.user_entry = ctk.CTkEntry(login_form, 
                                     width=300, 
                                     height=40,
                                     font=("Arial", 14))
        self.user_entry.insert(0, "Amalia")  # Establecer el valor predeterminado
        self.user_entry.pack(pady=10)
        
        ctk.CTkButton(login_form, 
                     text="Iniciar", 
                     command=self.start_client,
                     height=40,
                     font=("Arial", 14, "bold")).pack(pady=10, fill="x")

    def start_client(self):
        user_id = self.user_entry.get().strip()
        if not user_id:
            messagebox.showerror("Error", "El ID de usuario no puede estar vacío.")
            return
        if len(user_id) > 20:
            messagebox.showerror("Error", "El ID no puede tener más de 20 caracteres.")
            return
            
        try:
            self.client = LCPClient(user_id)
            self.login_frame.destroy()
            self._build_main_interface()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo iniciar el cliente: {str(e)}")

    def _build_main_interface(self):
        # Configurar grid principal
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        
        # Frame izquierdo (lista de peers)
        self.left_frame = ctk.CTkFrame(self.root, width=200, corner_radius=0)
        self.left_frame.grid(row=0, column=0, sticky="nsew")
        self.left_frame.grid_propagate(False)
        
        # Frame para los botones superiores
        top_buttons_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        top_buttons_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkButton(top_buttons_frame, 
                      text="Actualizar", 
                      command=self.update_peers,
                      width=80).pack(side="left", padx=2)
        ctk.CTkButton(top_buttons_frame, 
                      text="Global", 
                      command=self.set_global_chat,
                      width=80).pack(side="left", padx=2)
        
        # Lista de peers
        self.peer_listbox = ctk.CTkScrollableFrame(self.left_frame)
        self.peer_listbox.pack(fill="both", expand=True, padx=5, pady=5)
        self.peer_buttons = {}  # Para almacenar los botones de peers
        
        # Botón de salir
        ctk.CTkButton(self.left_frame, 
                     text="Salir", 
                     command=self.shutdown,
                     fg_color="red",
                     hover_color="dark red").pack(fill="x", padx=5, pady=5)
        
        # Frame derecho (chat)
        self.right_frame = ctk.CTkFrame(self.root, corner_radius=0)
        self.right_frame.grid(row=0, column=1, sticky="nsew")
        
        # Header del chat
        self.header_frame = ctk.CTkFrame(self.right_frame, height=50, corner_radius=0)
        self.header_frame.pack(fill="x")
        self.header_frame.pack_propagate(False)
        
        self.header_label = ctk.CTkLabel(self.header_frame, 
                                       text="Chat Global", 
                                       font=("Arial", 16, "bold"))
        self.header_label.pack(side="left", padx=20, pady=10)
        
        # Área de chat
        self.chat_frame = ctk.CTkScrollableFrame(self.right_frame)
        self.chat_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Frame de entrada de mensaje
        self.input_frame = ctk.CTkFrame(self.right_frame, height=70)
        self.input_frame.pack(fill="x", padx=10, pady=10)
        
        self.message_entry = ctk.CTkEntry(self.input_frame, 
                                         placeholder_text="Escribe un mensaje...",
                                         height=40,
                                         font=("Arial", 14))
        self.message_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.message_entry.bind("<Return>", lambda e: self.send_message())
        
        btn_frame = ctk.CTkFrame(self.input_frame, fg_color="transparent", width=100)
        btn_frame.pack(side="right")
        
        self.send_btn = ctk.CTkButton(btn_frame, 
                                     text="Enviar", 
                                     command=self.send_message,
                                     width=80,
                                     height=40)
        self.send_btn.pack(pady=2)
        
        self.file_btn = ctk.CTkButton(btn_frame, 
                                     text="Archivo", 
                                     command=self.send_file,
                                     width=80,
                                     height=40)
        self.file_btn.pack(pady=2)
        
        # Iniciar actualización automática
        Thread(target=self._auto_refresh, daemon=True).start()
        self.update_peers()

    def update_peers(self):
        if not self.client:
            return
            
        # Limpiar peer_buttons
        for widget in self.peer_listbox.winfo_children():
            widget.destroy()
        self.peer_buttons = {}
        
        # Agregar botón para chat global
        global_btn = ctk.CTkButton(self.peer_listbox,
                                  text="Chat Global",
                                  command=self.set_global_chat,
                                  fg_color="green" if self.global_chat_active else None,
                                  anchor="w")
        global_btn.pack(fill="x", pady=2, padx=2)
        self.peer_buttons["global"] = global_btn
        
        # Agregar peers
        for peer in self.client.peers:
            display_name = peer
            if peer in self.unread_counts and self.unread_counts[peer] > 0:
                display_name += f" ({self.unread_counts[peer]})"
                
            btn = ctk.CTkButton(self.peer_listbox,
                               text=display_name,
                               command=lambda p=peer: self._select_peer(p),
                               fg_color="#2b2b2b" if peer == self.active_peer else None,
                               anchor="w")
            btn.pack(fill="x", pady=2, padx=2)
            self.peer_buttons[peer] = btn

    def _select_peer(self, peer_id):
        self.active_peer = peer_id
        self.global_chat_active = False
        self.unread_counts.pop(peer_id, None)
        self.update_peers()
        self._refresh_chat()
        self.header_label.configure(text=f"Chat con {peer_id}")

    def set_global_chat(self):
        self.active_peer = None
        self.global_chat_active = True
        self._refresh_chat()
        self.update_peers()
        self.header_label.configure(text="Chat Global")

    def send_message(self):
        message = self.message_entry.get().strip()
        if not message:
            return
            
        target = self.active_peer or chr(255)*20
        Thread(target=self._send_message_thread, args=(target, message), daemon=True).start()

    def _send_message_thread(self, target, message):
        try:
            self.client.send_message(target, message)
            self.root.after(0, lambda: self.message_entry.delete(0, "end"))
            self._refresh_chat()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def send_file(self):
        if not self.active_peer:
            messagebox.showinfo("Info", "Selecciona un peer para enviar archivo.")
            return
            
        filepath = filedialog.askopenfilename()
        if filepath:
            Thread(target=self.client.send_file, args=(self.active_peer, filepath), daemon=True).start()
            messagebox.showinfo("Éxito", f"Archivo {filepath} enviado a {self.active_peer}")

    def _refresh_chat(self):
        if not self.client:
            return
            
        # Limpiar chat
        for widget in self.chat_frame.winfo_children():
            widget.destroy()
            
        for sender, message, timestamp in self.client.message_history:
            # Determinar si mostrar el mensaje en el chat actual
            show_message = False
            if self.global_chat_active and sender != self.client.user_id.decode('utf-8').strip():
                show_message = True
                tag = 'left'
            elif sender == self.client.user_id.decode('utf-8').strip():
                show_message = True
                tag = 'right'
            elif sender == self.active_peer:
                show_message = True
                tag = 'left'
                
            if not show_message:
                continue
                
            # Frame para el mensaje
            msg_frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
            msg_frame.pack(fill="x", padx=5, pady=2)
            
            # Configurar alineación
            if tag == 'right':
                msg_frame.pack_configure(anchor="e")
                bg_color = "#0078d7"  # Azul para mensajes propios
                text_color = "white"
            else:
                msg_frame.pack_configure(anchor="w")
                bg_color = "#e1e1e1"  # Gris claro para mensajes recibidos
                text_color = "black"
                
            # Contenedor del mensaje
            container = ctk.CTkFrame(msg_frame, 
                                   fg_color=bg_color, 
                                   corner_radius=10)
            container.pack(padx=5, pady=2)
            
            # Nombre del remitente (solo si no es propio y no es chat global)
            if tag == 'left' and not self.global_chat_active:
                sender_label = ctk.CTkLabel(container,
                                          text=sender,
                                          text_color=text_color,
                                          font=("Arial", 10, "bold"),
                                          anchor="w")
                sender_label.pack(fill="x", padx=10, pady=(5, 0))
                
            # Contenido del mensaje
            msg_label = ctk.CTkLabel(container,
                                   text=message,
                                   text_color=text_color,
                                   font=("Arial", 12),
                                   wraplength=400,
                                   justify="left")
            msg_label.pack(fill="x", padx=10, pady=5)
            
            # Marca de tiempo
            time_label = ctk.CTkLabel(container,
                                    text=timestamp,
                                    text_color=text_color,
                                    font=("Arial", 8),
                                    anchor="e")
            time_label.pack(fill="x", padx=10, pady=(0, 5))

    def _auto_refresh(self):
        while True:
            if not self.client:
                time.sleep(1)
                continue
                
            prev_len = len(self.client.message_history)
            time.sleep(1)
            
            if len(self.client.message_history) > prev_len:
                last_sender = self.client.message_history[-1][0]
                current_user = self.client.user_id.decode('utf-8').strip()
                
                # Actualizar contador de no leídos
                if (not self.global_chat_active and 
                    self.active_peer != last_sender and 
                    last_sender != current_user):
                    self.unread_counts[last_sender] = self.unread_counts.get(last_sender, 0) + 1
                
                self._refresh_chat()
                self.update_peers()

    def shutdown(self):
        if messagebox.askyesno("Salir", "¿Estás seguro de que quieres salir?"):
            if self.client:
                self.client.shutdown()
            self.root.destroy()

if __name__ == "__main__":
    root = ctk.CTk()
    app = LCPGUI(root)
    root.mainloop()