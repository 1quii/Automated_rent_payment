from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class Tenant(models.Model):
    """
    Modelo para representar a un Inquilino.
    Almacena información básica y su ID de cliente en Stripe.
    """
    name = models.CharField(max_length=200, verbose_name="Nombre Completo")
    email = models.EmailField(unique=True, verbose_name="Correo Electrónico")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Teléfono")
    
    # ID del cliente en Stripe (cus_xxxxx)
    stripe_customer_id = models.CharField(
        max_length=100, 
        unique=True, 
        null=True, 
        blank=True,
        verbose_name="Stripe Customer ID"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Inquilino"
        verbose_name_plural = "Inquilinos"
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.email})"


class Property(models.Model):
    """
    Modelo para representar una Propiedad en alquiler.
    """
    address = models.CharField(max_length=300, verbose_name="Dirección Completa")
    description = models.TextField(blank=True, verbose_name="Descripción")
    
    # Monto de renta mensual
    monthly_rent = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        verbose_name="Renta Mensual"
    )
    
    # Día del mes en que se debe realizar el cobro (1-31)
    billing_day = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        default=1,
        verbose_name="Día de Cobro",
        help_text="Día del mes para realizar el cobro (1-31)"
    )
    
    is_available = models.BooleanField(default=True, verbose_name="Disponible")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Propiedad"
        verbose_name_plural = "Propiedades"
        ordering = ['address']
    
    def __str__(self):
        return f"{self.address} - ${self.monthly_rent}/mes"


class Agreement(models.Model):
    """
    Modelo para representar un Contrato de Alquiler.
    Relaciona un Inquilino con una Propiedad y gestiona la suscripción en Stripe.
    """
    STATUS_CHOICES = [
        ('active', 'Activo'),
        ('inactive', 'Inactivo'),
        ('pending', 'Pendiente'),
        ('cancelled', 'Cancelado'),
        ('past_due', 'Pago Vencido'),
    ]
    
    tenant = models.ForeignKey(
        Tenant, 
        on_delete=models.PROTECT,
        related_name='agreements',
        verbose_name="Inquilino"
    )
    
    property = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name='agreements',
        verbose_name="Propiedad"
    )
    
    start_date = models.DateField(verbose_name="Fecha de Inicio")
    end_date = models.DateField(null=True, blank=True, verbose_name="Fecha de Fin")
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Estado"
    )
    
    # ID de la suscripción en Stripe (sub_xxxxx)
    stripe_subscription_id = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Stripe Subscription ID"
    )
    
    # ID del precio/plan en Stripe (price_xxxxx)
    stripe_price_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Stripe Price ID"
    )
    
    notes = models.TextField(blank=True, verbose_name="Notas")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Contrato"
        verbose_name_plural = "Contratos"
        ordering = ['-created_at']
        # Asegura que una propiedad no tenga múltiples contratos activos
        constraints = [
            models.UniqueConstraint(
                fields=['property'],
                condition=models.Q(status='active'),
                name='unique_active_agreement_per_property'
            )
        ]
    
    def __str__(self):
        return f"Contrato: {self.tenant.name} - {self.property.address}"
    
    def is_active(self):
        """Verifica si el contrato está activo"""
        return self.status == 'active'


class PaymentHistory(models.Model):
    """
    Modelo para registrar el historial de pagos.
    Se actualiza automáticamente mediante webhooks de Stripe.
    """
    PAYMENT_STATUS_CHOICES = [
        ('succeeded', 'Exitoso'),
        ('failed', 'Fallido'),
        ('pending', 'Pendiente'),
        ('refunded', 'Reembolsado'),
    ]
    
    agreement = models.ForeignKey(
        Agreement,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name="Contrato"
    )
    
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Monto"
    )
    
    status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        verbose_name="Estado"
    )
    
    # ID del pago en Stripe (pi_xxxxx o ch_xxxxx)
    stripe_payment_id = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Stripe Payment ID"
    )
    
    payment_date = models.DateTimeField(default=timezone.now, verbose_name="Fecha de Pago")
    failure_reason = models.TextField(blank=True, verbose_name="Razón de Fallo")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Historial de Pago"
        verbose_name_plural = "Historial de Pagos"
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"Pago {self.status} - ${self.amount} - {self.payment_date.strftime('%Y-%m-%d')}"