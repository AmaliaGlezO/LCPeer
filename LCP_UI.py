import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
from threading import Thread
from LCPeer_3 import LCPClient
import time
import threading

class LCPGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("LCPeer - Chat y Transferencia de Archivos")
        self.root.geometry("800x550")
        self.root.configure(bg="#eaeaea")

        self.client = None
        self._build_login()

    def _build_login(self):
        self.login_frame = tk.Frame(self.root, bg="#eaeaea", padx=20, pady=20)
        self.login_frame.pack(pady=100)

        tk.Label(self.login_frame, text="Ingresa tu ID (max 20 caracteres):", bg="#eaeaea", font=("Helvetica", 12),).pack()
        self.user_entry = tk.Entry(self.login_frame, font=("Helvetica", 14), width=30, bd=2, relief="groove")
        self.user_entry.insert(0, "Amalia")
        self.user_entry.pack(pady=10)

        tk.Button(
            self.login_frame, text="Iniciar", font=("Helvetica", 12),
            command=self.start_client, bg="#4CAF50", fg="white", bd=0, padx=10
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
        self.left_frame = tk.Frame(self.root, bg="#ffffff", width=200)
        self.left_frame.pack(side=tk.LEFT, fill=tk.Y)

        self.right_frame = tk.Frame(self.root, bg="#f8f9fa")
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.peer_listbox = tk.Listbox(self.left_frame, font=("Helvetica", 12), bg="#f0f0f0", bd=2, relief="groove")
        self.peer_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        tk.Button(self.left_frame, text="Actualizar pares", command=self.update_peers, bg="#2196F3", fg="white", bd=0, padx=10).pack(pady=5)
        tk.Button(self.left_frame, text="Cerrar", command=self.shutdown, bg="#f44336", fg="white", bd=0, padx=10).pack(pady=5)

        self.chat_area = scrolledtext.ScrolledText(self.right_frame, state='disabled', font=("Helvetica", 12), bg="#ffffff", wrap=tk.WORD)
        self.chat_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.message_entry = tk.Entry(self.right_frame, font=("Helvetica", 12), bd=2, relief="groove")
        self.message_entry.pack(fill=tk.X, padx=10, pady=(0, 5))
        self.message_entry.bind("<Return>", lambda event: self.send_message())

        button_frame = tk.Frame(self.right_frame, bg="#f8f9fa")
        button_frame.pack(pady=10)

        self.send_msg_btn = tk.Button(
            button_frame, text="Enviar Mensaje", command=self.send_message,
            bg="#4CAF50", fg="white", bd=0, font=("Helvetica", 12), width=18, height=2
        )
        self.send_msg_btn.pack(side=tk.LEFT, padx=10)

        self.send_file_btn = tk.Button(
            button_frame, text="Enviar Archivo", command=self.send_file,
            bg="#2196F3", fg="white", bd=0, font=("Helvetica", 12), width=18, height=2
        )
        self.send_file_btn.pack(side=tk.LEFT, padx=10)

        Thread(target=self._auto_refresh_history, daemon=True).start()

    def update_peers(self):
        self.peer_listbox.delete(0, tk.END)
        for peer_id in self.client.peers:
            self.peer_listbox.insert(tk.END, peer_id)

    def get_selected_peer(self):
        selected = self.peer_listbox.curselection()
        if not selected:
            messagebox.showwarning("Advertencia", "Selecciona un peer primero.")
            return None
        return self.peer_listbox.get(selected[0])

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
            self.client.send_message(peer_id, message)
            self.root.after(0, lambda: self.message_entry.delete(0, tk.END))
            self._refresh_history()
            
            # Imprimir en el área de chat
            self.chat_area.config(state='normal')
            self.chat_area.insert(tk.END, f"Mensaje enviado a {peer_id}: {message}\n")
            self.chat_area.config(state='disabled')
            
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
            self.client.send_file(peer_id, filepath)
        except Exception as e:
            messagebox.showerror("Error al enviar archivo", str(e))
        finally:
            self._set_interaction_state(True)

    def _refresh_history(self):
        self.chat_area.config(state='normal')
        self.chat_area.delete(1.0, tk.END)
        for sender, message, timestamp in self.client.message_history:
            time_str = timestamp.strftime("%H:%M:%S")
            self.chat_area.insert(tk.END, f"[{time_str}] {sender}: {message}\n")
        self.chat_area.config(state='disabled')

    def _auto_refresh_history(self):
        while True:
            self._refresh_history()
            time.sleep(1)

    def _set_interaction_state(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.send_msg_btn.config(state=state)
        self.send_file_btn.config(state=state)
        self.message_entry.config(state=state)

    def shutdown(self):
        if self.client:
            self.client.shutdown()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = LCPGUI(root)
    root.mainloop()
