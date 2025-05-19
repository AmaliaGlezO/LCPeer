import customtkinter as ctk  
from tkinter import filedialog, messagebox 
from threading import Thread  
from LCPeer import LCPClient  
import time  
import threading 
import json  
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
        self.is_updating = False
        self.history_dir = "chat_history"
        self._create_history_dir()
        self._build_login()

    def _create_history_dir(self):
        """Crea el directorio para guardar los historiales si no existe"""
        if not os.path.exists(self.history_dir):
            os.makedirs(self.history_dir)
            print(f"Directorio de historial creado: {self.history_dir}")

        # Crear archivo para mensajes broadcast si no existe
        broadcast_file = os.path.join(self.history_dir, "Broadcast.json")
        if not os.path.exists(broadcast_file):
            with open(broadcast_file, "w") as f:
                json.dump([], f)
            print(f"Archivo de historial de broadcasts creado: {broadcast_file}")

    def _get_history_file(self, peer_id):
        """Devuelve la ruta del archivo de historial para un peer específico"""
        return os.path.join(self.history_dir, f"{peer_id}.json")

    def _save_message(self, peer_id, sender, message, timestamp=None):
        """Guarda un mensaje en el historial del peer especificado"""
        if timestamp is None:
            timestamp = datetime.now().isoformat()

        history_file = self._get_history_file(peer_id)
        history = self._load_peer_history(peer_id)

        # Evitar duplicados verificando si el mensaje ya existe
        for msg in history:
            if (
                msg.get("timestamp") == timestamp
                and msg.get("sender") == sender
                and msg.get("message") == message
            ):
                return  

        # Añadir el nuevo mensaje al historial
        history.append({"timestamp": timestamp, "sender": sender, "message": message})

        with open(history_file, "w") as f:
            json.dump(history, f, indent=2)

    def _load_peer_history(self, peer_id):
        """Carga el historial de mensajes con un peer específico"""
        history_file = self._get_history_file(peer_id)

        if not os.path.exists(history_file):
            return []

        try:
            with open(history_file, "r") as f:
                return json.load(f)
        except:
            return []

    def _display_peer_history(self, peer_id):
        """Muestra el historial de mensajes con un peer en el área de chat"""
        history = self._load_peer_history(peer_id)
        self.chat_area.configure(state="normal")
        self.chat_area.delete("1.0", "end")

        if not history and peer_id == "Broadcast":
            self.chat_area.insert("end", "No hay mensajes broadcast aún.\n")
            self.current_peer = "Broadcast"
        else:
    
            messages_to_show = history[-10:] if len(history) > 10 else history

            for msg in messages_to_show:
                timestamp = datetime.fromisoformat(msg["timestamp"]).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                self.chat_area.insert(
                    "end", f"[{timestamp}] {msg['sender']}: {msg['message']}\n"
                )

        self.chat_area.configure(state="disabled")
        self.chat_area.see("end")

    def _build_login(self):
        self.login_frame = ctk.CTkFrame(self.root)
        self.login_frame.pack(pady=100, padx=20, fill="both", expand=True)

        ctk.CTkLabel(
            self.login_frame,
            text="Ingresa tu ID (max 20 caracteres):",
            font=("Helvetica", 12),
        ).pack(pady=(0, 10))

        self.user_entry = ctk.CTkEntry(
            self.login_frame, font=("Helvetica", 14), width=300
        )
        self.user_entry.insert(0, "Amalia")
        self.user_entry.pack(pady=10)

        ctk.CTkButton(
            self.login_frame,
            text="Iniciar",
            font=("Helvetica", 12),
            command=self.start_client,
            fg_color="#4CAF50",
            hover_color="#45a049",
        ).pack(pady=5)


    def start_client(self):
        """Inicia el cliente P2P con el ID proporcionado"""
        user_id = self.user_entry.get().strip()
        if not user_id:
            messagebox.showerror("Error", "El ID de usuario no puede estar vacío.")
            return

        self.client = LCPClient(user_id)  
        
        try:
            self.client.register_message_callback(self._on_message_received)
        except Exception as e:
            print(f"Error registrando callback: {e}")
        self.login_frame.destroy()  
        self._build_main_interface()  

    def _build_main_interface(self):
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        self.left_frame = ctk.CTkFrame(self.root, width=200, corner_radius=0)
        self.left_frame.grid(row=0, column=0, sticky="nswe")
        self.left_frame.grid_rowconfigure(1, weight=1)

        self.right_frame = ctk.CTkFrame(self.root, corner_radius=0)
        self.right_frame.grid(row=0, column=1, sticky="nswe")
        self.right_frame.grid_rowconfigure(0, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)

        self.peer_list_title = ctk.CTkLabel(
            self.left_frame, 
            text="PEERS DISPONIBLES", 
            font=("Helvetica", 14, "bold"),
            pady=10
        )
        self.peer_list_title.grid(row=0, column=0, sticky="we", padx=5, pady=(5, 10))

        self.peer_listbox = ctk.CTkScrollableFrame(self.left_frame)
        self.peer_listbox.grid(row=1, column=0, padx=5, pady=5, sticky="nswe")
        self.peer_listbox.grid_columnconfigure(0, weight=1)

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

        self.chat_header = ctk.CTkLabel(
            self.right_frame, 
            text="Seleccione un peer para chatear",
            font=("Helvetica", 14, "bold"),
            height=40,
            corner_radius=5
        )
        self.chat_header.grid(row=0, column=0, padx=10, pady=5, sticky="nwe")

        self.chat_area = ctk.CTkTextbox(
            self.right_frame, 
            font=("Helvetica", 12), 
            wrap="word",
            height=400
        )
        self.chat_area.grid(row=1, column=0, padx=10, pady=5, sticky="nswe")
        self.chat_area.configure(state="disabled")

        self.message_entry = ctk.CTkEntry(
            self.right_frame, 
            font=("Helvetica", 12),
            placeholder_text="Escribe tu mensaje aquí..."
        )

        self.message_entry.grid(row=2, column=0, padx=10, pady=(5, 5), sticky="we")
        self.message_entry.bind("<Return>", lambda event: self.send_message())

        button_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        button_frame.grid(row=3, column=0, pady=5, sticky="we")
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)
        button_frame.grid_columnconfigure(2, weight=1)

        self.send_msg_btn = ctk.CTkButton(
            button_frame, 
            text="Enviar Mensaje", 
            command=self.send_message,
            fg_color="#2c3e50",
            hover_color="#34495e",
            font=("Helvetica", 12)
        )
        self.send_msg_btn.grid(row=0, column=0, padx=5, sticky="we")

        self.send_msg_btn = ctk.CTkButton(
            button_frame, 
            text="Enviar Mensaje", 
            command=self.send_message,
            fg_color="#2c3e50",
            hover_color="#34495e",
            font=("Helvetica", 12)
        )
        self.send_msg_btn.grid(row=0, column=0, padx=5, sticky="we")

        self.send_file_btn = ctk.CTkButton(
            button_frame, 
            text="Enviar Archivo", 
            command=self.send_file,
            fg_color="#2c3e50",
            hover_color="#34495e",
            font=("Helvetica", 12)
        )
        self.send_file_btn.grid(row=0, column=1, padx=5, sticky="we")

        self.broadcast_btn = ctk.CTkButton(
            button_frame,
            text="Enviar a Todos",
            command=self.send_broadcast,
            fg_color="#2c3e50",
            hover_color="#34495e",
            font=("Helvetica", 12),
        )
        self.broadcast_btn.grid(row=0, column=2, padx=5, sticky="we")

        Thread(target=self._auto_refresh_history, daemon=True).start()

    def send_broadcast(self):
        """Envía el mensaje actual como broadcast a todos los peers"""
        message = self.message_entry.get().strip()
        if not message:
            messagebox.showwarning("Advertencia", "El mensaje no puede estar vacío.")
            return

        if not hasattr(self, "client") or not self.client:
            messagebox.showerror("Error", "No hay conexión activa.")
            return

        if not messagebox.askyesno(
            "Confirmar", f"¿Enviar este mensaje a TODOS los peers?\n\n{message}"
        ):
            return

        try:
            threading.Thread(
                target=self.client.uno_a_muchos, args=(message,), daemon=True
            ).start()

            self.show_broadcast_history()

            self.message_entry.delete(0, "end")

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo enviar el broadcast: {str(e)}")

    def update_peers(self):
        for widget in self.peer_listbox.winfo_children():
            widget.destroy()

        broadcast_frame = ctk.CTkFrame(self.peer_listbox, corner_radius=5)
        broadcast_frame.pack(fill="x", pady=5, padx=2)

        broadcast_label = ctk.CTkLabel(
            broadcast_frame,
            text="📢 Mensajes Broadcast",
            font=("Helvetica", 12, "bold"),
            text_color=("#3B8ED0", "#3B8ED0"),
        )
        broadcast_label.pack(fill="x", pady=5, padx=5)
        broadcast_frame.bind("<Button-1>", lambda e: self.show_broadcast_history())
        broadcast_label.bind("<Button-1>", lambda e: self.show_broadcast_history())

        separator = ctk.CTkFrame(self.peer_listbox, height=1)
        separator.pack(fill="x", pady=8, padx=10)

        for peer_id in self.client.peers:
            peer_frame = ctk.CTkFrame(self.peer_listbox, fg_color="transparent")
            peer_frame.pack(fill="x", pady=2)
            
            if peer_id in self.client.peers:
                status_circle = ctk.CTkLabel(
                    peer_frame,
                    text="●",
                    font=("Helvetica", 12),
                    text_color="#27ae60",
                    width=20
                )
                status_circle.pack(side="left", padx=(5,0))

            peer_label = ctk.CTkLabel(
                peer_frame,
                text=peer_id,
                font=("Helvetica", 12),
                fg_color="#2c3e50",
                corner_radius=5,
                height=30
            )
            peer_label.pack(side="left", fill="x", expand=True, padx=(5,5))
            
            peer_frame.bind("<Button-1>", lambda e, pid=peer_id: self._select_peer(pid))
            peer_label.bind("<Button-1>", lambda e, pid=peer_id: self._select_peer(pid))


    def _select_peer(self, peer_id):
        """Selecciona un peer y carga su historial de chat"""
        for widget in self.peer_listbox.winfo_children():
            try:
                if isinstance(widget, ctk.CTkLabel):
                    widget.configure(fg_color="transparent")
                
                elif isinstance(widget, ctk.CTkFrame):
                    widget.configure(fg_color="transparent")
            except Exception as e:
                print(f"Error al limpiar widget: {e}")

        for widget in self.peer_listbox.winfo_children():
            try:
                if isinstance(widget, ctk.CTkLabel) and hasattr(widget, "cget"):
                    if widget.cget("text") == peer_id:
                        widget.configure(fg_color="#3B8ED0")
                        self.current_peer = peer_id
                        self._display_peer_history(peer_id)
                        return
            except Exception as e:
                print(f"Error al procesar widget: {e}")

        self.current_peer = peer_id
        self._display_peer_history(peer_id)

    def get_selected_peer(self):
        """Devuelve el peer seleccionado actualmente o None"""
        return self.current_peer

    def show_broadcast_history(self):
        """Muestra el historial de mensajes broadcast"""
        print("Mostrando historial de mensajes broadcast")
        self.current_peer = "Broadcast"

        for widget in self.peer_listbox.winfo_children():
            try:
                widget.configure(fg_color="transparent")

                if isinstance(widget, ctk.CTkFrame) and widget.winfo_children():
                    for child in widget.winfo_children():
                        if isinstance(child, ctk.CTkLabel) and hasattr(child, "cget"):
                            try:
                                if "Broadcast" in child.cget("text"):
                                    widget.configure(fg_color=("#3B8ED0", "#1F538D"))
                                    break
                            except Exception as e:
                                print(f"Error al verificar texto del hijo: {e}")
            except Exception as e:
                print(f"Error al configurar widget en broadcast history: {e}")

        # Asegurarse de que existe un archivo de historial para broadcasts
        history_file = self._get_history_file("Broadcast")
        if not os.path.exists(os.path.dirname(history_file)):
            os.makedirs(os.path.dirname(history_file))

        if not os.path.exists(history_file):
            with open(history_file, "w") as f:
                json.dump([], f)

        # Mostrar el historial
        self._display_peer_history("Broadcast")

    def send_message(self):
        peer_id = self.get_selected_peer()
        if not peer_id:
            return

        message = self.message_entry.get().strip()
        if not message:
            return

        threading.Thread(
            target=self._send_message_thread, args=(peer_id, message), daemon=True
        ).start()

    def _send_message_thread(self, peer_id, message):
        try:
            self._set_interaction_state(False)
            timestamp = datetime.now()
            self.client.send_message(peer_id, message)
            self.root.after(0, lambda: self.message_entry.delete(0, "end"))

            # Mostrar en el chat
            self.chat_area.configure(state="normal")
            self.chat_area.insert("end", f"[Tú]: {message}\n")
            self.chat_area.configure(state="disabled")

            # Guardar en historial
            self._save_message(
                peer_id,
                self.client.user_id.decode("utf-8").strip(),
                message,
                timestamp.isoformat(),
            )

        except Exception as e:
            messagebox.showerror("Error al enviar mensaje", str(e))
        finally:
            self._set_interaction_state(True)

    def send_file(self):
        peer_id = self.get_selected_peer()
        if not peer_id:
            return

        filepath = filedialog.askopenfilename()
        if not filepath:
            return

        threading.Thread(
            target=self._send_file_thread, args=(peer_id, filepath), daemon=True
        ).start()

    def _send_file_thread(self, peer_id, filepath):
        try:
            self._set_interaction_state(False)
            timestamp = datetime.now()
            self.client.send_file(peer_id, filepath)

            # Guardar en historial
            filename = os.path.basename(filepath)
            self._save_message(
                peer_id,
                self.client.user_id.decode("utf-8").strip(),
                f"Archivo enviado: {filename}",
                timestamp.isoformat(),
            )

            # Mostrar en el chat
            self.chat_area.configure(state="normal")
            self.chat_area.insert("end", f"[Tú] Archivo enviado: {filename}\n")
            self.chat_area.configure(state="disabled")

        except Exception as e:
            messagebox.showerror("Error al enviar archivo", str(e))
        finally:
            self._set_interaction_state(True)

    def _refresh_history(self):
        """Actualiza el historial cuando llegan nuevos mensajes"""
        for peer_id in self.client.peers:
            peer_messages = [
                msg
                for msg in self.client.message_history
                if msg[0] == peer_id or msg[0] == self.client.normalizar(peer_id)
            ]
            existing_history = self._load_peer_history(peer_id)

            new_messages = []
            for msg_data in peer_messages:
                sender, message_text, timestamp = msg_data
                is_new = True

                for existing_msg in existing_history:
                    if (
                        existing_msg.get("message") == message_text
                        and existing_msg.get("sender") == sender
                    ):
                        is_new = False
                        break

                if is_new:
                    new_messages.append(msg_data)

            if new_messages:
                for sender, message, timestamp in new_messages:
                    self._save_message(peer_id, sender, message, timestamp.isoformat())

                if self.current_peer and self.current_peer == peer_id:
                    self._display_peer_history(peer_id)

    def _auto_refresh_history(self):
        while True:
            self._refresh_history()
            time.sleep(1)

    def _on_message_received(self, sender_id, message):
        """Callback que se ejecuta cuando se recibe un mensaje nuevo"""
        try:
            timestamp = datetime.now()
            print(f"CALLBACK - Mensaje recibido de {sender_id}: {message}")

            if sender_id == "Broadcast" or sender_id == "Broadcast:Enviado":
                is_sent = sender_id == "Broadcast:Enviado"
                display_sender = "Tú (Broadcast)" if is_sent else "Broadcast"

                self._save_message(
                    "Broadcast", display_sender, message, timestamp.isoformat()
                )

                if not is_sent:
                    self.root.after(
                        0,
                        lambda: messagebox.showinfo(
                            "Mensaje Broadcast",
                            f"Broadcast recibido: {message[:100]}...",
                        ),
                    )

                if self.current_peer == "Broadcast":
                    self.root.after(0, lambda: self._display_peer_history("Broadcast"))
            else:
                self._save_message(sender_id, sender_id, message, timestamp.isoformat())
                if self.current_peer == sender_id:
                    self.root.after(
                        0, lambda: self._update_chat_display(sender_id, message)
                    )
                else:
                    self.root.after(
                        0,
                        lambda: messagebox.showinfo(
                            "Nuevo mensaje",
                            f"Mensaje recibido de {sender_id}:\n{message[:50]}...",
                        ),
                    )
        except Exception as e:
            print(f"Error procesando mensaje recibido: {e}")

    def _update_chat_display(self, sender_id, message):
        """Actualiza la visualización del chat con un nuevo mensaje"""
        if self.current_peer == sender_id:
            self.chat_area.configure(state="normal")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.chat_area.insert("end", f"[{timestamp}] {sender_id}: {message}\n")
            self.chat_area.configure(state="disabled")
            self.chat_area.see("end")

    def _set_interaction_state(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.send_msg_btn.configure(state=state)
        self.send_file_btn.configure(state=state)
        self.broadcast_btn.configure(state=state)
        self.message_entry.configure(state=state)

    def shutdown(self):
        if self.client:
            self.client.shutdown()
        self.root.destroy()


if __name__ == "__main__":
    root = ctk.CTk()
    app = LCPGUI(root)
    root.mainloop()
