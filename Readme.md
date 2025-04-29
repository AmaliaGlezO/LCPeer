# 🖇️ LCPeer: Chat P2P para Redes Locales  
**Asignatura**: Sistemas Computacionales y Redes (2024)  
**Autor**: [Amalia González Ortega]  
**Fecha de entrega**: 19 de mayo de 2024  



## 🎯 Objetivo  
Crear un sistema de mensajería **descentralizado** que funcione en redes LAN sin servidores centrales, con autodescubrimiento automático y funcionalidades avanzadas como grupos e historial.  

---

## ✅ Funcionalidades Implementadas  

### 🔹 Básicas (Requisitos)  
[✅] **Protocolo LCP**  
- Formato de mensajes: `TIMESTAMP|USUARIO|TIPO|CONTENIDO`.  
- Autenticación básica con nicknames.  

[✅] **Autodescubrimiento LAN**  
- Detección automática de usuarios usando UDP broadcast.  
- Actualización dinámica de la lista de contactos.  

### 🔹 Adicionales (Extras)  
[✅] **Modo uno-a-muchos**  
- Envío de mensajes a todos los usuarios con una sola transmisión.  

[✅] **Mensajes grupales**  
- Creación/unión a grupos (`/create`, `/join`).  
- Envío de mensajes a grupos específicos (`@grupo mensaje`).  

[✅] **Historial offline**  
- Almacena últimos 10 mensajes por chat/grupo (SQLite).  

[🔄] **Interfaz gráfica (GUI)**  
- Listado de usuarios/grupos en tiempo real.  
- Pestañas para chats individuales y grupales.  

---

## 🧩 Arquitectura  
```plaintext
           [Broadcast UDP]
                │
[Usuario A] ────┼───► [Usuario B]  
   │  ▲           ▲  │  
   ▼  └───[LAN]───┘  ▼  
[GUI]            [Historial SQLite]  