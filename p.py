import customtkinter as ctk
from tkinter import filedialog, messagebox
from threading import Thread
from LCPeer_3 import LCPClient
import time
import threading
import os
from datetime import datetime

class LCPGUI:
    def __init__(self, root):
        """
        Inicializa la interfaz gráfica del cliente P2P
        Args:
            root: Ventana principal de la aplicación
        """
        self.root = root
        self.root.title("LCPeer - Chat y Transferencia de Archivos")
        self.root.geometry("900x600")  # Tamaño inicial de la ventana
        
        # Configuración del tema visual
        ctk.set_appearance_mode("System")  # Usa el tema del sistema
        ctk.set_default_color_theme("blue")  # Tema de color azul
        
        self.client = None  # Cliente P2P (se inicializará después del login)
        self.current_peer = None  # Peer seleccionado actualmente
        self.is_updating = False  # Flag para controlar actualizaciones simultáneas
        self._build_login()  # Construye la pantalla de login

    def _build_login(self):
        """Construye la pantalla de inicio de sesión"""
        self.login_frame = ctk.CTkFrame(self.root)
        self.login_frame.pack(pady=100, padx=20, fill="both", expand=True)

        # Etiqueta para el campo de ID
        ctk.CTkLabel(self.login_frame, text="Ingresa tu ID (max 20 caracteres):", 
                     font=("Helvetica", 12)).pack(pady=(0, 10))
        
        # Campo de entrada para el ID
        self.user_entry = ctk.CTkEntry(self.login_frame, font=("Helvetica", 14), width=300)
        self.user_entry.insert(0, "Amalia")  # Valor por defecto
        self.user_entry.pack(pady=10)

        # Botón de inicio
        ctk.CTkButton(
            self.login_frame, text="Iniciar", font=("Helvetica", 12),
            command=self.start_client, fg_color="#4CAF50", hover_color="#45a049"
        ).pack(pady=5)

    def start_client(self):
        """Inicia el cliente P2P con el ID proporcionado"""
        user_id = self.user_entry.get().strip()
        if not user_id:
            messagebox.showerror("Error", "El ID de usuario no puede estar vacío.")
            return

        self.client = LCPClient(user_id)  # Crea el cliente P2P
        self.login_frame.destroy()  # Elimina la pantalla de login
        self._build_main_interface()  # Construye la interfaz principal

    def _build_main_interface(self):
        """Construye la interfaz principal de la aplicación"""
        # Configuración del grid principal
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        # Frame izquierdo para lista de peers y botones
        self.left_frame = ctk.CTkFrame(self.root, width=200, corner_radius=0)
        self.left_frame.grid(row=0, column=0, sticky="nswe")
        self.left_frame.grid_rowconfigure(1, weight=1)

        # Frame derecho para chat y entrada de mensajes
        self.right_frame = ctk.CTkFrame(self.root, corner_radius=0)
        self.right_frame.grid(row=0, column=1, sticky="nswe")
        self.right_frame.grid_rowconfigure(0, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)

        # Título de la lista de peers
        self.peer_list_title = ctk.CTkLabel(
            self.left_frame, 
            text="PEERS DISPONIBLES", 
            font=("Helvetica", 14, "bold"),
            pady=10
        )
        self.peer_list_title.grid(row=0, column=0, sticky="we", padx=5, pady=(5, 10))

        # Contenedor de la lista de peers
        self.peer_listbox = ctk.CTkScrollableFrame(self.left_frame)
        self.peer_listbox.grid(row=1, column=0, padx=5, pady=5, sticky="nswe")
        self.peer_listbox.grid_columnconfigure(0, weight=1)

        # Opción de broadcast
        self.broadcast_peer = ctk.CTkLabel(
            self.peer_listbox, 
            text="[ENVIAR A TODOS]", 
            font=("Helvetica", 12),
            fg_color="#2c3e50",
            corner_radius=5,
            height=30
        )
        self.broadcast_peer.pack(fill="x", pady=2)
        self.broadcast_peer.bind("<Button-1>", lambda e: self._select_peer("BROADCAST"))

        # Botones de control
        ctk.CTkButton(
            self.left_frame, 
            text="Actualizar lista", 
            command=self.update_peers, 
            fg_color="#2c3e50",
            hover_color="#34495e"
        ).grid(row=2, column=0, padx=5, pady=5, sticky="we")

        ctk.CTkButton(
            self.left_frame, 
            text="Cerrar", 
            command=self.shutdown, 
            fg_color="#c0392b",
            hover_color="#e74c3c"
        ).grid(row=3, column=0, padx=5, pady=5, sticky="we")

        # Encabezado del chat
        self.chat_header = ctk.CTkLabel(
            self.right_frame, 
            text="Seleccione un peer para chatear",
            font=("Helvetica", 14, "bold"),
            height=40,
            corner_radius=5
        )
        self.chat_header.grid(row=0, column=0, padx=10, pady=5, sticky="nwe")

        # Área de chat
        self.chat_area = ctk.CTkTextbox(
            self.right_frame, 
            font=("Helvetica", 12), 
            wrap="word",
            height=400
        )
        self.chat_area.grid(row=1, column=0, padx=10, pady=5, sticky="nswe")
        self.chat_area.configure(state="disabled")

        # Campo de entrada de mensaje
        self.message_entry = ctk.CTkEntry(
            self.right_frame, 
            font=("Helvetica", 12),
            placeholder_text="Escribe tu mensaje aquí..."
        )
        self.message_entry.grid(row=2, column=0, padx=10, pady=(5, 5), sticky="we")
        self.message_entry.bind("<Return>", lambda event: self.send_message())

        # Frame para botones de acción
        button_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        button_frame.grid(row=3, column=0, pady=5, sticky="we")
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

        # Botón de enviar mensaje
        self.send_msg_btn = ctk.CTkButton(
            button_frame, 
            text="Enviar Mensaje", 
            command=self.send_message,
            fg_color="#2c3e50",
            hover_color="#34495e",
            font=("Helvetica", 12)
        )
        self.send_msg_btn.grid(row=0, column=0, padx=5, sticky="we")

        # Botón de enviar archivo
        self.send_file_btn = ctk.CTkButton(
            button_frame, 
            text="Enviar Archivo", 
            command=self.send_file,
            fg_color="#2c3e50",
            hover_color="#34495e",
            font=("Helvetica", 12)
        )
        self.send_file_btn.grid(row=0, column=1, padx=5, sticky="we")

        # Inicia el hilo de actualización automática
        Thread(target=self._auto_refresh_chat, daemon=True).start()

    def update_peers(self):
        """Actualiza la lista de peers disponibles"""
        # Limpia la lista existente (excepto la opción de broadcast)
        for widget in self.peer_listbox.winfo_children()[1:]:
            widget.destroy()
            
        # Añade los peers actuales con indicador de estado
        for peer_id in self.client.peers:
            # Frame para contener el círculo y el nombre
            peer_frame = ctk.CTkFrame(self.peer_listbox, fg_color="transparent")
            peer_frame.pack(fill="x", pady=2)
            
            # Círculo de estado (verde si está en línea)
            if peer_id in self.client.peers:
                status_circle = ctk.CTkLabel(
                    peer_frame,
                    text="●",
                    font=("Helvetica", 12),
                    text_color="#27ae60",
                    width=20
                )
                status_circle.pack(side="left", padx=(5,0))
            
            # Etiqueta con el nombre del peer
            peer_label = ctk.CTkLabel(
                peer_frame,
                text=peer_id,
                font=("Helvetica", 12),
                fg_color="#2c3e50",
                corner_radius=5,
                height=30
            )
            peer_label.pack(side="left", fill="x", expand=True, padx=(5,5))
            
            # Vincula eventos de clic
            peer_frame.bind("<Button-1>", lambda e, pid=peer_id: self._select_peer(pid))
            peer_label.bind("<Button-1>", lambda e, pid=peer_id: self._select_peer(pid))

    def _select_peer(self, peer_id):
        """
        Selecciona un peer y actualiza la interfaz
        Args:
            peer_id: ID del peer seleccionado
        """
        # Resetea los resaltados de todos los peers
        for widget in self.peer_listbox.winfo_children():
            if isinstance(widget, ctk.CTkFrame):
                for child in widget.winfo_children():
                    if isinstance(child, ctk.CTkLabel) and child.cget("text") != "●":
                        child.configure(fg_color="#2c3e50")
        
        # Resalta el peer seleccionado
        for widget in self.peer_listbox.winfo_children():
            if peer_id == "BROADCAST" and widget.cget("text") == "[ENVIAR A TODOS]":
                widget.configure(fg_color="#000000")
                self.current_peer = "BROADCAST"
                self.chat_header.configure(
                    text="Chat Global",
                    font=("Helvetica", 16, "bold")
                )
                self.chat_area.configure(state="normal")
                self.chat_area.delete("1.0", "end")
                self.chat_area.configure(state="disabled")
                # Ejecutamos la función send_broadcast cuando se selecciona BROADCAST
                self.send_broadcast()
                break
            elif isinstance(widget, ctk.CTkFrame):
                for child in widget.winfo_children():
                    if isinstance(child, ctk.CTkLabel) and child.cget("text") == peer_id:
                        child.configure(fg_color="#34495e")
                        self.current_peer = peer_id
                        self.chat_header.configure(
                            text=f"Chat con {peer_id}",
                            font=("Helvetica", 16, "bold")
                        )
                        self._display_chat_history(peer_id)
                        break

    def _display_chat_history(self, peer_id):
        """
        Muestra el historial de chat con el peer seleccionado
        Args:
            peer_id: ID del peer cuyo historial se mostrará
        """
        self.chat_area.configure(state="normal")
        self.chat_area.delete("1.0", "end")
        
        # Añade fecha y hora de inicio
        self.chat_area.insert("end", f"Conversación iniciada: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n")
        
        # Muestra los mensajes del historial
        for msg in self.client.message_history:
            if msg[0] == peer_id or (msg[0] == "BROADCAST" and peer_id in self.client.peers):
                is_own_message = msg[0] == self.client.user_id.decode("utf-8").strip()
                
                if is_own_message:
                    self.chat_area.insert("end", f"Tú • {msg[2].strftime('%H:%M')}\n", "right")
                    self.chat_area.insert("end", f"{msg[1]}\n\n", "right_blue")
                else:
                    self.chat_area.insert("end", f"{msg[0]} • {msg[2].strftime('%H:%M')}\n", "left")
                    self.chat_area.insert("end", f"{msg[1]}\n\n", "left_gray")
        
        # Configura los estilos de los mensajes
        self.chat_area.tag_configure("right", justify="right")
        self.chat_area.tag_configure("left", justify="left")
        self.chat_area.tag_configure("right_blue", justify="right", foreground="#2c3e50")
        self.chat_area.tag_configure("left_gray", justify="left", foreground="#757575")
        
        self.chat_area.configure(state="disabled")
        self.chat_area.see("end")

    def send_message(self):
        """Envía un mensaje al peer seleccionado"""
        message = self.message_entry.get().strip()
        if not message:
            return

        if not self.current_peer:
            messagebox.showwarning("Advertencia", "Selecciona un peer primero.")
            return

        if self.current_peer == "BROADCAST":
            self.send_broadcast()
            return

        threading.Thread(target=self._send_message_thread, args=(self.current_peer, message), daemon=True).start()

    def _send_message_thread(self, peer_id, message):
        """
        Maneja el envío de mensajes en un hilo separado
        Args:
            peer_id: ID del peer destinatario
            message: Mensaje a enviar
        """
        try:
            self._set_interaction_state(False)
            self.client.send_message(peer_id, message)
            self.root.after(0, lambda: self.message_entry.delete(0, "end"))
            
            # Muestra el mensaje en el chat
            self.chat_area.configure(state="normal")
            msg_frame = ctk.CTkFrame(self.chat_area, fg_color="transparent")
            msg_frame.pack(fill="x", padx=10, pady=2, anchor="e")
            
            bubble = ctk.CTkFrame(msg_frame, fg_color="#2c3e50", corner_radius=15)
            bubble.pack(padx=5, pady=2, anchor="e")
            
            msg_label = ctk.CTkLabel(
                bubble,
                text=message,
                text_color="white",
                font=("Helvetica", 12),
                wraplength=400,
                justify="left"
            )
            msg_label.pack(padx=10, pady=5)
            
            self.chat_area.configure(state="disabled")
            self.chat_area.see("end")
            
        except Exception as e:
            messagebox.showerror("Error al enviar mensaje", str(e))
        finally:
            self._set_interaction_state(True)

    def send_broadcast(self):
        """Envía un mensaje a todos los peers"""
        message = self.message_entry.get().strip()
        if not message:
            messagebox.showwarning("Advertencia", "El mensaje no puede estar vacío.")
            return
            
        if not hasattr(self, 'client') or not self.client:
            messagebox.showerror("Error", "No hay conexión activa.")
            return
            
        # Confirmación antes de enviar
        if not messagebox.askyesno("Confirmar", f"¿Enviar este mensaje a TODOS los peers?\n\n{message}"):
            return
            
        try:
            self._set_interaction_state(False)
            threading.Thread(target=self._send_broadcast_thread, args=(message,), daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo enviar el broadcast: {str(e)}")
            self._set_interaction_state(True)

    def _send_broadcast_thread(self, message):
        """
        Maneja el envío de broadcast en un hilo separado
        Args:
            message: Mensaje a enviar
        """
        try:
            self.client.uno_a_muchos(message)
            self.client.message_history.append(
                (self.client.user_id.decode("utf-8").strip(), message, datetime.now())
            )
            self.root.after(0, lambda: self._update_broadcast_ui(message))
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error al enviar broadcast: {str(e)}"))
        finally:
            self.root.after(0, lambda: self._set_interaction_state(True))

    def _update_broadcast_ui(self, message):
        """
        Actualiza la interfaz después de enviar un broadcast
        Args:
            message: Mensaje enviado
        """
        self.message_entry.delete(0, "end")
        
        self.chat_area.configure(state="normal")
        self.chat_area.insert("end", f"Tú [BROADCAST] • {datetime.now().strftime('%H:%M')}\n", "right")
        self.chat_area.insert("end", f"{message}\n\n", "right_blue")
        self.chat_area.configure(state="disabled")
        self.chat_area.see("end")

    def send_file(self):
        """Inicia el proceso de envío de archivo"""
        if not self.current_peer or self.current_peer == "BROADCAST":
            messagebox.showwarning("Advertencia", "Selecciona un peer individual para enviar archivos.")
            return

        filepath = filedialog.askopenfilename()
        if not filepath:
            return

        threading.Thread(target=self._send_file_thread, args=(self.current_peer, filepath), daemon=True).start()

    def _send_file_thread(self, peer_id, filepath):
        """
        Maneja el envío de archivos en un hilo separado
        Args:
            peer_id: ID del peer destinatario
            filepath: Ruta del archivo a enviar
        """
        try:
            self._set_interaction_state(False)
            self.client.send_file(peer_id, filepath)
            
            filename = os.path.basename(filepath)
            self.chat_area.configure(state="normal")
            self.chat_area.insert("end", f"Tú [ARCHIVO]: {filename}\n")
            self.chat_area.configure(state="disabled")
            self.chat_area.see("end")
            
        except Exception as e:
            messagebox.showerror("Error al enviar archivo", str(e))
        finally:
            self._set_interaction_state(True)

    def _auto_refresh_chat(self):
        """Actualiza automáticamente el chat y la lista de peers"""
        if not self.is_updating:
            self.is_updating = True
            try:
                if self.current_peer and self.current_peer != "BROADCAST":
                    self._display_chat_history(self.current_peer)
                self.update_peers()
            finally:
                self.is_updating = False
        self.root.after(1000, self._auto_refresh_chat)

    def _set_interaction_state(self, enabled: bool):
        """
        Habilita o deshabilita los controles de la interfaz
        Args:
            enabled: True para habilitar, False para deshabilitar
        """
        state = "normal" if enabled else "disabled"
        self.send_msg_btn.configure(state=state)
        self.send_file_btn.configure(state=state)
        self.message_entry.configure(state=state)

    def shutdown(self):
        """Cierra la aplicación y limpia recursos"""
        if self.client:
            self.client.shutdown()
        self.root.destroy()

if __name__ == "__main__":
    root = ctk.CTk()
    app = LCPGUI(root)
    root.mainloop()