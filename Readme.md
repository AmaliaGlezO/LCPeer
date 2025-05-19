 
# 🖇️ LCPeer: Chat P2P para Redes Locales

## 👥 Autor
- **Nombre**: Amalia González Ortega
- **Asignatura**: Sistemas Computacionales y Redes
- **Fecha**: 2024

## 📝 Descripción
LCPeer es una aplicación de mensajería peer-to-peer (P2P) diseñada para funcionar en redes locales (LAN). Utiliza el protocolo LCP (Local Chat Protocol) para permitir la comunicación directa entre usuarios sin necesidad de servidores centrales.

## 🎯 Características Principales

### 🔹 Comunicación P2P
- **Chat Individual**: Comunicación directa entre dos usuarios
- **Broadcast**: Envío de mensajes a todos los usuarios conectados
- **Transferencia de Archivos**: Compartir archivos entre usuarios

### 🔹 Interfaz Gráfica
- **Diseño Moderno**: Interfaz construida con CustomTkinter
- **Lista de Usuarios**: Muestra los peers disponibles en tiempo real
- **Indicadores de Estado**: Muestra qué usuarios están en línea
- **Historial de Chat**: Visualización de conversaciones anteriores

### 🔹 Sistema de Historial
- **Almacenamiento Local**: Guarda las conversaciones en archivos JSON
- **Persistencia**: Mantiene el historial entre sesiones
- **Organización**: Historial separado por usuario y broadcast

### 🔹 Características Técnicas
- **Protocolo LCP**: Implementación del protocolo local de chat
- **Autodescubrimiento**: Detección automática de usuarios en la red
- **Comunicación Bidireccional**: UDP para control y TCP para archivos
- **Manejo de Errores**: Sistema robusto de manejo de excepciones


### Funcionalidades
1. **Chat Individual**
   - Seleccionar un usuario de la lista
   - Escribir mensaje y presionar "Enviar Mensaje"
   - Ver historial de la conversación

2. **Broadcast**
   - Escribir mensaje
   - Presionar "Enviar a Todos"
   - Confirmar envío

3. **Transferencia de Archivos**
   - Seleccionar usuario
   - Presionar "Enviar Archivo"
   - Elegir archivo a enviar

## 🛠️ Arquitectura
```plaintext
[Interfaz Gráfica (GUI)]
        │
        ▼
[Cliente LCP (P2P)] ←→ [Red Local]
        │
        ▼
[Almacenamiento Local]
    - Historial JSON
    - Archivos Recibidos
```



# 🎯 Objetivo  
Crear un sistema de mensajería **descentralizado** que funcione en redes LAN sin servidores centrales, con autodescubrimiento automático y funcionalidades avanzadas como grupos e historial.  

---


---

## 🧩 Arquitectura  
```plaintext
           [Broadcast UDP]
                │
[Usuario A] ────┼───► [Usuario B]  
   │  ▲           ▲  │  
   ▼  └───[LAN]───┘  ▼  
[GUI]            [Historial]  