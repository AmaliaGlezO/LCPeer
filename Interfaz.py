import tkinter as tk
from tkinter import filedialog, messagebox, Canvas
from threading import Thread
from LCPeer_3 import LCPClient
import time
import threading

class LCPGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("LCPeer Chat")
        self.root.geometry("900x600")
        self.root.configure(bg="#ececec")

        self.client = None
        self.active_peer = None
        self.unread_counts = {}

        self._build_login()

    def _build_login(self):
        self.login_frame = tk.Frame(self.root, bg="#ececec")
        self.login_frame.pack(expand=True)

        tk.Label(self.login_frame, text="Ingresa tu ID (max 20 caracteres):", bg="#ececec", font=("Helvetica", 12)).pack(pady=10)
        self.user_entry = tk.Entry(self.login_frame, font=("Helvetica", 14), width=30)
        self.user_entry.pack(pady=10)
        tk.Button(self.login_frame, text="Iniciar", command=self.start_client, bg="#4CAF50", fg="white", font=("Helvetica", 12)).pack(pady=10)

    def start_client(self):
        user_id = self.user_entry.get().strip()
        if not user_id:
            messagebox.showerror("Error", "El ID de usuario no puede estar vacío.")
            return
        self.client = LCPClient(user_id)
        self.login_frame.destroy()
        self._build_main_interface()

    def _build_main_interface(self):
        self.left_frame = tk.Frame(self.root, bg="#f0f0f0", width=200)
        self.left_frame.pack(side=tk.LEFT, fill=tk.Y)

        self.peer_listbox = tk.Listbox(self.left_frame, font=("Helvetica", 12))
        self.peer_listbox.pack(fill=tk.BOTH, expand=True)
        self.peer_listbox.bind("<<ListboxSelect>>", self._on_peer_select)

        tk.Button(self.left_frame, text="Actualizar", command=self.update_peers).pack(fill=tk.X)
        tk.Button(self.left_frame, text="Enviar a todos", command=self.set_global_chat).pack(fill=tk.X)
        tk.Button(self.left_frame, text="Salir", command=self.shutdown).pack(fill=tk.X)

        self.right_frame = tk.Frame(self.root, bg="#ffffff")
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.header_label = tk.Label(self.right_frame, text="Chat Global", bg="#dddddd", font=("Helvetica", 14), anchor='w')
        self.header_label.pack(fill=tk.X)

        self.chat_canvas = Canvas(self.right_frame, bg="#ffffff")
        self.chat_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.chat_frame = tk.Frame(self.chat_canvas, bg="#ffffff")
        self.chat_window = self.chat_canvas.create_window((0, 0), window=self.chat_frame, anchor='nw')

        self.chat_frame.bind("<Configure>", lambda e: self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all")))

        self.message_entry = tk.Entry(self.right_frame, font=("Helvetica", 12))
        self.message_entry.pack(fill=tk.X, padx=10, pady=(5, 0))
        self.message_entry.bind("<Return>", lambda e: self.send_message())

        btn_frame = tk.Frame(self.right_frame, bg="#ffffff")
        btn_frame.pack(pady=5)

        self.send_btn = tk.Button(btn_frame, text="⬆", command=self.send_message, font=("Helvetica", 14), bg="#4CAF50", fg="white", width=4, height=1)
        self.send_btn.pack(side=tk.LEFT, padx=5)
        self.file_btn = tk.Button(btn_frame, text="➕", command=self.send_file, font=("Helvetica", 14), bg="#2196F3", fg="white", width=4, height=1)
        self.file_btn.pack(side=tk.LEFT, padx=5)

        Thread(target=self._auto_refresh, daemon=True).start()

    def update_peers(self):
        self.peer_listbox.delete(0, tk.END)
        for peer in self.client.peers:
            display_name = peer
            if peer in self.unread_counts:
                display_name += f" ({self.unread_counts[peer]})"
            self.peer_listbox.insert(tk.END, display_name)

    def _on_peer_select(self, event):
        selection = self.peer_listbox.curselection()
        if not selection:
            return
        peer_display = self.peer_listbox.get(selection[0])
        peer_id = peer_display.split(" (")[0]
        self.active_peer = peer_id
        self.unread_counts.pop(peer_id, None)
        self.update_peers()
        self._refresh_chat()
        self.header_label.config(text=f"Chat con {peer_id}")

    def set_global_chat(self):
        self.active_peer = None
        self._refresh_chat()
        self.header_label.config(text="Chat Global")

    def send_message(self):
        message = self.message_entry.get().strip()
        if not message:
            return
        target = self.active_peer or chr(255)*20
        Thread(target=self._send_message_thread, args=(target, message), daemon=True).start()

    def _send_message_thread(self, target, message):
        try:
            self.client.send_message(target, message)
            self.root.after(0, lambda: self.message_entry.delete(0, tk.END))
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

    def _refresh_chat(self):
        for widget in self.chat_frame.winfo_children():
            widget.destroy()

        for sender, message, timestamp in self.client.message_history:
            if self.active_peer is None and sender != self.client.user_id.decode('utf-8').strip():
                tag = 'left'
            elif sender == self.client.user_id.decode('utf-8').strip():
                tag = 'right'
            elif sender == self.active_peer:
                tag = 'left'
            else:
                continue

            bubble = tk.Label(
                self.chat_frame,
                text=message,
                bg="#d1ffd1" if tag == 'right' else "#e1eaff",
                anchor='e' if tag == 'right' else 'w',
                justify='left',
                wraplength=400,
                padx=10,
                pady=5,
                font=("Helvetica", 11),
                bd=1,
                relief="solid"
            )
            bubble.pack(anchor=tag, pady=2, padx=10, fill=tk.NONE)

    def _auto_refresh(self):
        while True:
            prev_len = len(self.client.message_history)
            time.sleep(1)
            if len(self.client.message_history) > prev_len:
                last_sender = self.client.message_history[-1][0]
                if self.active_peer != last_sender:
                    self.unread_counts[last_sender] = self.unread_counts.get(last_sender, 0) + 1
                self._refresh_chat()
                self.update_peers()

    def shutdown(self):
        if self.client:
            self.client.shutdown()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = LCPGUI(root)
    root.mainloop()
