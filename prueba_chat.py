import subprocess
import time
import sys
import os

def iniciar_chat(nombre_usuario):
    """Inicia una instancia del chat con el nombre de usuario especificado"""
    # Construir el comando
    comando = [sys.executable, "InterfazChatQt.py"]
    
    # Iniciar el proceso
    proceso = subprocess.Popen(comando, 
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             text=True)
    
    # Esperar un momento para que la ventana se abra
    time.sleep(2)
    
    # Enviar el nombre de usuario
    proceso.stdin.write(nombre_usuario + "\n")
    proceso.stdin.flush()
    
    return proceso

def main():
    print("Iniciando prueba del chat con dos usuarios...")
    
    # Iniciar dos instancias del chat
    usuario1 = iniciar_chat("Usuario1")
    usuario2 = iniciar_chat("Usuario2")
    
    print("Chats iniciados. Puedes probar la comunicación entre ambos usuarios.")
    print("Presiona Ctrl+C para terminar la prueba.")
    
    try:
        # Mantener el script corriendo
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nTerminando prueba...")
        usuario1.terminate()
        usuario2.terminate()
        print("Prueba terminada.")

if __name__ == "__main__":
    main() 