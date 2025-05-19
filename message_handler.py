import threading
import queue


class MessageHandler:
    """
    Clase utilitaria para manejar suscripciones a eventos de mensajes
    """

    def __init__(self):
        self._message_callbacks = []
        self._callback_lock = threading.Lock()
        self._message_queue = queue.Queue()
        threading.Thread(target=self._process_messages, daemon=True).start()

    def register_callback(self, callback):
        """Registra una función que será llamada cuando se reciba un mensaje"""
        with self._callback_lock:
            self._message_callbacks.append(callback)

    def unregister_callback(self, callback):
        """Elimina una función de la lista de callbacks"""
        with self._callback_lock:
            if callback in self._message_callbacks:
                self._message_callbacks.remove(callback)

    def notify_message(self, sender_id, message):
        """Notifica un nuevo mensaje a todos los callbacks registrados"""
        self._message_queue.put((sender_id, message))

    def _process_messages(self):
        """Procesa mensajes en la cola y notifica a los callbacks"""
        while True:
            try:
                sender_id, message = self._message_queue.get()
                with self._callback_lock:
                    for callback in self._message_callbacks:
                        try:
                            callback(sender_id, message)
                        except Exception as e:
                            print(f"Error en callback de mensajes: {e}")
                self._message_queue.task_done()
            except Exception as e:
                print(f"Error en procesador de mensajes: {e}")
