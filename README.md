# 🏢 Sistema de Gestión de Alquileres con Cobro Automático

Sistema de gestión de propiedades en alquiler con pagos recurrentes automáticos mediante Stripe.

## 📋 Características

- ✅ Gestión de inquilinos y propiedades
- ✅ Contratos de alquiler digitales
- ✅ Cobros automáticos mensuales con Stripe
- ✅ Historial completo de pagos
- ✅ Notificaciones de pagos exitosos/fallidos

## 🛠️ Stack Tecnológico

- **Backend:** Django 5.0
- **Base de Datos:** PostgreSQL / SQLite
- **Pagos:** Stripe Subscriptions API
- **Frontend:** Django Templates (HTML/CSS)

## 🚀 Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/TU_USUARIO/TU_REPOSITORIO.git
cd TU_REPOSITORIO
```

### 2. Crear entorno virtual

```bash
python -m venv venv

# En Windows:
venv\Scripts\activate

# En Mac/Linux:
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

Crea un archivo `.env` en la raíz del proyecto:

```env
SECRET_KEY=tu-secret-key-django-aqui
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Stripe Keys (obtener de https://dashboard.stripe.com/test/apikeys)
STRIPE_PUBLIC_KEY=pk_test_xxxxxxxxxxxxx
STRIPE_SECRET_KEY=sk_test_xxxxxxxxxxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxx

# Base de datos
DATABASE_URL=postgresql://usuario:password@localhost:5432/nombre_db
```

### 5. Ejecutar migraciones

```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Crear superusuario

```bash
python manage.py createsuperuser
```

### 7. Ejecutar servidor de desarrollo

```bash
python manage.py runserver
```

Visita: `http://127.0.0.1:8000`

## 🔐 Seguridad

⚠️ **IMPORTANTE:**
- NUNCA subas tu archivo `.env` a GitHub
- NUNCA almacenes información de tarjetas en la base de datos
- Usa Stripe.js para tokenizar tarjetas desde el frontend
- Valida siempre los webhooks de Stripe

## 📁 Estructura del Proyecto

```
proyecto/
│
├── manage.py
├── requirements.txt
├── .env (NO SUBIR A GIT)
├── .gitignore
├── README.md
│
├── rental_app/
│   ├── models.py          # Modelos de datos
│   ├── views.py           # Vistas
│   ├── stripe_service.py  # Integración con Stripe
│   ├── urls.py
│   └── templates/
│
└── config/
    ├── settings.py
    ├── urls.py
    └── wsgi.py
```

## 🔧 Configuración de Webhooks Stripe

1. Ir a: https://dashboard.stripe.com/test/webhooks
2. Agregar endpoint: `https://tudominio.com/webhooks/stripe/`
3. Seleccionar eventos:
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
   - `customer.subscription.deleted`
   - `customer.subscription.updated`
4. Copiar el `Signing secret` y agregarlo a `.env`

## 📝 Uso

### Crear una suscripción:

```python
from rental_app.stripe_service import StripeSubscriptionService

# payment_method_id viene del frontend (Stripe Elements)
result = StripeSubscriptionService.create_subscription(
    agreement=mi_contrato,
    payment_method_id='pm_xxxxxxxxxxxxx'
)
```

## 🤝 Contribuir

Las contribuciones son bienvenidas. Por favor:

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT.

## 📧 Contacto

Tu Nombre - [@tu_twitter](https://twitter.com/tu_twitter)

Link del Proyecto: [https://github.com/TU_USUARIO/TU_REPOSITORIO](https://github.com/TU_USUARIO/TU_REPOSITORIO)
