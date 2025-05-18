import customtkinter as ctk
from tkinter import filedialog, messagebox
from threading import Thread
from LCPeer_3 import LCPClient
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
        self.history_dir = "chat_history"
        self._create_history_dir()
        self._build_login()

    def _create_history_dir(self):
        """Crea el directorio para guardar los historiales si no existe"""
        if not os.path.exists(self.history_dir):
            os.makedirs(self.history_dir)

    def _get_history_file(self, peer_id):
        """Devuelve la ruta del archivo de historial para un peer específico"""
        return os.path.join(self.history_dir, f"{peer_id}.json")

    def _save_message(self, peer_id, sender, message, timestamp=None):
        """Guarda un mensaje en el historial del peer especificado"""
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        
        history_file = self._get_history_file(peer_id)
        history = self._load_peer_history(peer_id)
        
        history.append({
            "timestamp": timestamp,
            "sender": sender,
            "message": message
        })
        
        with open(history_file, 'w') as f:
            json.dump(history, f, indent=2)

    def _load_peer_history(self, peer_id):
        """Carga el historial de mensajes con un peer específico"""
        history_file = self._get_history_file(peer_id)
        
        if not os.path.exists(history_file):
            return []
            
        try:
            with open(history_file, 'r') as f:
                return json.load(f)
        except:
            return []

    def _display_peer_history(self, peer_id):
        """Muestra el historial de mensajes con un peer en el área de chat"""
        history = self._load_peer_history(peer_id)
        self.chat_area.configure(state="normal")
        self.chat_area.delete("1.0", "end")
        
        for msg in history:
            timestamp = datetime.fromisoformat(msg["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
            self.chat_area.insert("end", f"[{timestamp}] {msg['sender']}: {msg['message']}\n")
        
        self.chat_area.configure(state="disabled")
        self.chat_area.see("end")

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

        # Peer list
        self.peer_listbox = ctk.CTkScrollableFrame(self.left_frame, label_text="Peers disponibles")
        self.peer_listbox.grid(row=1, column=0, padx=5, pady=5, sticky="nswe")
        self.peer_listbox.grid_columnconfigure(0, weight=1)

        # Buttons in left frame
        ctk.CTkButton(
            self.left_frame, text="Actualizar pares", 
            command=self.update_peers, fg_color="#2196F3", hover_color="#1976D2"
        ).grid(row=2, column=0, padx=5, pady=5, sticky="we")

        ctk.CTkButton(
            self.left_frame, text="Cerrar", 
            command=self.shutdown, fg_color="#f44336", hover_color="#d32f2f"
        ).grid(row=3, column=0, padx=5, pady=5, sticky="we")

        # Chat area
        self.chat_area = ctk.CTkTextbox(self.right_frame, font=("Helvetica", 12), wrap="word")
        self.chat_area.grid(row=0, column=0, padx=10, pady=10, sticky="nswe")
        self.chat_area.configure(state="disabled")

        # Message entry
        self.message_entry = ctk.CTkEntry(self.right_frame, font=("Helvetica", 12))
        self.message_entry.grid(row=1, column=0, padx=10, pady=(0, 5), sticky="we")
        self.message_entry.bind("<Return>", lambda event: self.send_message())

        # Button frame
        button_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        button_frame.grid(row=2, column=0, pady=10, sticky="we")
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)
        button_frame.grid_columnconfigure(2, weight=1)

        self.send_msg_btn = ctk.CTkButton(
            button_frame, text="Enviar Mensaje", command=self.send_message,
            fg_color="#4CAF50", hover_color="#45a049", font=("Helvetica", 12)
        )
        self.send_msg_btn.grid(row=0, column=0, padx=5, sticky="we")

        self.send_file_btn = ctk.CTkButton(
            button_frame, text="Enviar Archivo", command=self.send_file,
            fg_color="#2196F3", hover_color="#1976D2", font=("Helvetica", 12)
        )
        self.send_file_btn.grid(row=0, column=1, padx=5, sticky="we")

        self.broadcast_btn = ctk.CTkButton(
            button_frame, text="Enviar a Todos", command=self.send_broadcast,
            fg_color="#9C27B0", hover_color="#7B1FA2", font=("Helvetica", 12)
        )
        self.broadcast_btn.grid(row=0, column=2, padx=5, sticky="we")

        Thread(target=self._auto_refresh_history, daemon=True).start()

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
            # Usar el método uno_a_muchos del cliente
            threading.Thread(target=self.client.uno_a_muchos, args=(message,), daemon=True).start()
            
            # Mostrar en el chat
            self.chat_area.configure(state="normal")
            self.chat_area.insert("end", f"[Broadcast enviado a todos]: {message}\n")
            self.chat_area.configure(state="disabled")
            
            # Guardar en historial de cada peer
            for peer_id in self.client.peers:
                self._save_message(peer_id, "Broadcast", message)
            
            # Limpiar el campo de mensaje
            self.message_entry.delete(0, "end")
            
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo enviar el broadcast: {str(e)}")

    def update_peers(self):
        for widget in self.peer_listbox.winfo_children():
            widget.destroy()
            
        for peer_id in self.client.peers:
            peer_label = ctk.CTkLabel(self.peer_listbox, text=peer_id, font=("Helvetica", 12))
            peer_label.pack(fill="x", pady=2)
            peer_label.bind("<Button-1>", lambda e, pid=peer_id: self._select_peer(pid))

    def _select_peer(self, peer_id):
        """Selecciona un peer y carga su historial de chat"""
        for widget in self.peer_listbox.winfo_children():
            widget.configure(fg_color="transparent")
            
        for widget in self.peer_listbox.winfo_children():
            if widget.cget("text") == peer_id:
                widget.configure(fg_color="#3B8ED0")
                self.current_peer = peer_id
                self._display_peer_history(peer_id)
                break

    def get_selected_peer(self):
        if not self.current_peer:
            messagebox.showwarning("Advertencia", "Selecciona un peer primero.")
            return None
        return self.current_peer

    def send_message(self):
        peer_id = self.get_selected_peer()
        if not peer_id:
            return

        message = self.message_entry.get().strip()
        if not message:
            return

        threading.Thread(target=self._send_message_thread, args=(peer_id, message), daemon=True).start()

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
            self._save_message(peer_id, self.client.user_id.decode("utf-8").strip(), message, timestamp.isoformat())
            
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

        threading.Thread(target=self._send_file_thread, args=(peer_id, filepath), daemon=True).start()

    def _send_file_thread(self, peer_id, filepath):
        try:
            self._set_interaction_state(False)
            timestamp = datetime.now()
            self.client.send_file(peer_id, filepath)
            
            # Guardar en historial
            filename = os.path.basename(filepath)
            self._save_message(peer_id, self.client.user_id.decode("utf-8").strip(), 
                             f"Archivo enviado: {filename}", timestamp.isoformat())
            
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
        if not self.current_peer:
            return
            
        # Solo actualizamos si hay nuevos mensajes
        current_count = len(self._load_peer_history(self.current_peer))
        new_messages = [msg for msg in self.client.message_history 
                       if msg[0] == self.current_peer and 
                       not any(m for m in self._load_peer_history(self.current_peer) 
                           if m["sender"] == msg[0] and m["message"] == msg[1])]
        
        if new_messages:
            for sender, message, timestamp in new_messages:
                self._save_message(self.current_peer, sender, message, timestamp.isoformat())
            
            if self.current_peer:
                self._display_peer_history(self.current_peer)

    def _auto_refresh_history(self):
        while True:
            self._refresh_history()
            time.sleep(1)

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