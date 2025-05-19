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
        self.root = root
        self.root.title("LCPeer - Chat y Transferencia de Archivos")
        self.root.geometry("900x600")
        
        # Configure appearance
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        
        self.client = None
        self.current_peer = None
        self.is_updating = False  # Flag para controlar actualizaciones
        self._build_login()

    def _build_login(self):
        self.login_frame = ctk.CTkFrame(self.root)
        self.login_frame.pack(pady=100, padx=20, fill="both", expand=True)

        ctk.CTkLabel(self.login_frame, text="Ingresa tu ID (max 20 caracteres):", 
                     font=("Helvetica", 12)).pack(pady=(0, 10))
        
        self.user_entry = ctk.CTkEntry(self.login_frame, font=("Helvetica", 14), width=300)
        self.user_entry.insert(0, "Amalia")
        self.user_entry.pack(pady=10)

        ctk.CTkButton(
            self.login_frame, text="Iniciar", font=("Helvetica", 12),
            command=self.start_client, fg_color="#4CAF50", hover_color="#45a049"
        ).pack(pady=5)

    def start_client(self):
        user_id = self.user_entry.get().strip()
        if not user_id:
            messagebox.showerror("Error", "El ID de usuario no puede estar vacío.")
            return

        self.client = LCPClient(user_id)
        self.login_frame.destroy()
        self._build_main_interface()

    def _build_main_interface(self):
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        # Left frame for peer list and buttons
        self.left_frame = ctk.CTkFrame(self.root, width=200, corner_radius=0)
        self.left_frame.grid(row=0, column=0, sticky="nswe")
        self.left_frame.grid_rowconfigure(1, weight=1)

        # Right frame for chat and message input
        self.right_frame = ctk.CTkFrame(self.root, corner_radius=0)
        self.right_frame.grid(row=0, column=1, sticky="nswe")
        self.right_frame.grid_rowconfigure(0, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)

        # Peer list title
        self.peer_list_title = ctk.CTkLabel(
            self.left_frame, 
            text="PEERS DISPONIBLES", 
            font=("Helvetica", 14, "bold"),
            pady=10
        )
        self.peer_list_title.grid(row=0, column=0, sticky="we", padx=5, pady=(5, 10))

        # Peer list container
        self.peer_listbox = ctk.CTkScrollableFrame(self.left_frame)
        self.peer_listbox.grid(row=1, column=0, padx=5, pady=5, sticky="nswe")
        self.peer_listbox.grid_columnconfigure(0, weight=1)

        # Add "Enviar a todos" option at the top of the peer list
        self.broadcast_peer = ctk.CTkLabel(
            self.peer_listbox, 
            text="[ENVIAR A TODOS]", 
            font=("Helvetica", 12),
            fg_color="#2c3e50",  # Azul oscuro elegante
            corner_radius=5,
            height=30
        )
        self.broadcast_peer.pack(fill="x", pady=2)
        self.broadcast_peer.bind("<Button-1>", lambda e: self._select_peer("BROADCAST"))

        # Buttons in left frame
        ctk.CTkButton(
            self.left_frame, 
            text="Actualizar lista", 
            command=self.update_peers, 
            fg_color="#2c3e50",  # Azul oscuro elegante
            hover_color="#34495e"  # Azul oscuro más claro para hover
        ).grid(row=2, column=0, padx=5, pady=5, sticky="we")

        ctk.CTkButton(
            self.left_frame, 
            text="Cerrar", 
            command=self.shutdown, 
            fg_color="#c0392b",  # Rojo oscuro
            hover_color="#e74c3c"  # Rojo más claro para hover
        ).grid(row=3, column=0, padx=5, pady=5, sticky="we")

        # Chat header
        self.chat_header = ctk.CTkLabel(
            self.right_frame, 
            text="Seleccione un peer para chatear",
            font=("Helvetica", 14, "bold"),
            height=40,
            corner_radius=5
        )
        self.chat_header.grid(row=0, column=0, padx=10, pady=5, sticky="nwe")

        # Chat area - Aumentado el tamaño
        self.chat_area = ctk.CTkTextbox(
            self.right_frame, 
            font=("Helvetica", 12), 
            wrap="word",
            height=400  # Altura fija más grande
        )
        self.chat_area.grid(row=1, column=0, padx=10, pady=5, sticky="nswe")
        self.chat_area.configure(state="disabled")

        # Message entry
        self.message_entry = ctk.CTkEntry(
            self.right_frame, 
            font=("Helvetica", 12),
            placeholder_text="Escribe tu mensaje aquí..."
        )
        self.message_entry.grid(row=2, column=0, padx=10, pady=(5, 5), sticky="we")
        self.message_entry.bind("<Return>", lambda event: self.send_message())

        # Button frame
        button_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        button_frame.grid(row=3, column=0, pady=5, sticky="we")
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

        self.send_msg_btn = ctk.CTkButton(
            button_frame, 
            text="Enviar Mensaje", 
            command=self.send_message,
            fg_color="#2c3e50",  # Azul oscuro elegante
            hover_color="#34495e",  # Azul oscuro más claro para hover
            font=("Helvetica", 12)
        )
        self.send_msg_btn.grid(row=0, column=0, padx=5, sticky="we")

        self.send_file_btn = ctk.CTkButton(
            button_frame, 
            text="Enviar Archivo", 
            command=self.send_file,
            fg_color="#2c3e50",  # Azul oscuro elegante
            hover_color="#34495e",  # Azul oscuro más claro para hover
            font=("Helvetica", 12)
        )
        self.send_file_btn.grid(row=0, column=1, padx=5, sticky="we")

        Thread(target=self._auto_refresh_chat, daemon=True).start()

    def update_peers(self):
        # Clear existing peers (except the broadcast option)
        for widget in self.peer_listbox.winfo_children()[1:]:
            widget.destroy()
            
        # Add current peers with online status
        for peer_id in self.client.peers:
            # Crear un frame para contener el círculo y el nombre
            peer_frame = ctk.CTkFrame(self.peer_listbox, fg_color="transparent")
            peer_frame.pack(fill="x", pady=2)
            
            # Crear el círculo de estado (solo si el peer está en línea)
            if peer_id in self.client.peers:  # Si está en la lista de peers, está en línea
                status_circle = ctk.CTkLabel(
                    peer_frame,
                    text="●",
                    font=("Helvetica", 12),
                    text_color="#27ae60",  # Verde para el círculo de estado
                    width=20
                )
                status_circle.pack(side="left", padx=(5,0))
            
            # Crear el nombre del peer
            peer_label = ctk.CTkLabel(
                peer_frame,
                text=peer_id,
                font=("Helvetica", 12),
                fg_color="#2c3e50",  # Azul oscuro para el fondo del nombre
                corner_radius=5,
                height=30
            )
            peer_label.pack(side="left", fill="x", expand=True, padx=(5,5))
            
            # Vincular el evento de clic al frame completo
            peer_frame.bind("<Button-1>", lambda e, pid=peer_id: self._select_peer(pid))
            peer_label.bind("<Button-1>", lambda e, pid=peer_id: self._select_peer(pid))

    def _select_peer(self, peer_id):
        """Selecciona un peer y actualiza la interfaz"""
        # Reset all peer highlights
        for widget in self.peer_listbox.winfo_children():
            if isinstance(widget, ctk.CTkFrame):  # Solo procesar frames de peers
                for child in widget.winfo_children():
                    if isinstance(child, ctk.CTkLabel) and child.cget("text") != "●":
                        child.configure(fg_color="#2c3e50")
        
        # Highlight selected peer
        for widget in self.peer_listbox.winfo_children():
            if peer_id == "BROADCAST" and widget.cget("text") == "[ENVIAR A TODOS]":
                widget.configure(fg_color="#000000")  # Negro cuando está seleccionado
                self.current_peer = "BROADCAST"
                self.chat_header.configure(
                    text="Chat Global",
                    font=("Helvetica", 16, "bold")
                )
                self.chat_area.configure(state="normal")
                self.chat_area.delete("1.0", "end")
                self.chat_area.configure(state="disabled")
                break
            elif isinstance(widget, ctk.CTkFrame):  # Es un frame de peer
                for child in widget.winfo_children():
                    if isinstance(child, ctk.CTkLabel) and child.cget("text") == peer_id:
                        child.configure(fg_color="#34495e")  # Azul más claro cuando está seleccionado
                        self.current_peer = peer_id
                        self.chat_header.configure(
                            text=f"Chat con {peer_id}",
                            font=("Helvetica", 16, "bold")
                        )
                        self._display_chat_history(peer_id)
                        break

    def _display_chat_history(self, peer_id):
        """Muestra el historial de chat con el peer seleccionado"""
        self.chat_area.configure(state="normal")
        self.chat_area.delete("1.0", "end")
        
        # Agregar fecha y hora de inicio de la conversación
        self.chat_area.insert("end", f"Conversación iniciada: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n")
        
        for msg in self.client.message_history:
            if msg[0] == peer_id or (msg[0] == "BROADCAST" and peer_id in self.client.peers):
                # Determinar si es mensaje propio o recibido
                is_own_message = msg[0] == self.client.user_id.decode("utf-8").strip()
                
                # Configurar el estilo del mensaje
                if is_own_message:
                    # Mensaje propio (derecha, azul)
                    self.chat_area.insert("end", f"Tú • {msg[2].strftime('%H:%M')}\n", "right")
                    self.chat_area.insert("end", f"{msg[1]}\n\n", "right_blue")
                else:
                    # Mensaje recibido (izquierda, gris)
                    self.chat_area.insert("end", f"{msg[0]} • {msg[2].strftime('%H:%M')}\n", "left")
                    self.chat_area.insert("end", f"{msg[1]}\n\n", "left_gray")
        
        # Configurar tags para el estilo de los mensajes
        self.chat_area.tag_configure("right", justify="right")
        self.chat_area.tag_configure("left", justify="left")
        self.chat_area.tag_configure("right_blue", justify="right", foreground="#2c3e50")
        self.chat_area.tag_configure("left_gray", justify="left", foreground="#757575")
        
        self.chat_area.configure(state="disabled")
        self.chat_area.see("end")

    def send_message(self):
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
        try:
            self._set_interaction_state(False)
            self.client.send_message(peer_id, message)
            self.root.after(0, lambda: self.message_entry.delete(0, "end"))
            
            # Mostrar en el chat con estilo de burbuja
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
        """Envía el mensaje actual como broadcast a todos los peers"""
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
            # Deshabilitar la interfaz durante el envío
            self._set_interaction_state(False)
            
            # Enviar el broadcast en un hilo separado
            threading.Thread(target=self._send_broadcast_thread, args=(message,), daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo enviar el broadcast: {str(e)}")
            self._set_interaction_state(True)

    def _send_broadcast_thread(self, message):
        """Maneja el envío de broadcast en un hilo separado"""
        try:
            # Enviar el mensaje
            self.client.uno_a_muchos(message)
            
            # Agregar el mensaje al historial
            self.client.message_history.append(
                (self.client.user_id.decode("utf-8").strip(), message, datetime.now())
            )
            
            # Actualizar la interfaz
            self.root.after(0, lambda: self._update_broadcast_ui(message))
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error al enviar broadcast: {str(e)}"))
        finally:
            self.root.after(0, lambda: self._set_interaction_state(True))

    def _update_broadcast_ui(self, message):
        """Actualiza la interfaz después de enviar un broadcast"""
        # Limpiar el campo de mensaje
        self.message_entry.delete(0, "end")
        
        # Mostrar en el chat
        self.chat_area.configure(state="normal")
        self.chat_area.insert("end", f"Tú [BROADCAST] • {datetime.now().strftime('%H:%M')}\n", "right")
        self.chat_area.insert("end", f"{message}\n\n", "right_blue")
        self.chat_area.configure(state="disabled")
        self.chat_area.see("end")

    def send_file(self):
        if not self.current_peer or self.current_peer == "BROADCAST":
            messagebox.showwarning("Advertencia", "Selecciona un peer individual para enviar archivos.")
            return

        filepath = filedialog.askopenfilename()
        if not filepath:
            return

        threading.Thread(target=self._send_file_thread, args=(self.current_peer, filepath), daemon=True).start()

    def _send_file_thread(self, peer_id, filepath):
        try:
            self._set_interaction_state(False)
            self.client.send_file(peer_id, filepath)
            
            # Mostrar en el chat
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
        self.root.after(1000, self._auto_refresh_chat)  # Programar siguiente actualización

    def _set_interaction_state(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.send_msg_btn.configure(state=state)
        self.send_file_btn.configure(state=state)
        self.message_entry.configure(state=state)

    def shutdown(self):
        if self.client:
            self.client.shutdown()
        self.root.destroy()

if __name__ == "__main__":
    root = ctk.CTk()
    app = LCPGUI(root)
    root.mainloop()