"""
Módulo de Integración con Stripe para Gestión de Suscripciones de Alquiler

IMPORTANTE - SEGURIDAD:
- NUNCA almacenes información de tarjetas de crédito en tu base de datos
- Usa Stripe.js o Stripe Elements en el frontend para tokenizar tarjetas
- Solo almacena IDs de Stripe (customer_id, subscription_id, etc.)
- Mantén tu STRIPE_SECRET_KEY segura (usa variables de entorno)
- Valida todos los webhooks con la firma de Stripe
"""

import stripe
from django.conf import settings
from django.db import transaction
from decimal import Decimal
from typing import Optional, Dict, Any
import logging

# Configurar Stripe con tu clave secreta
stripe.api_key = settings.STRIPE_SECRET_KEY

logger = logging.getLogger(__name__)


class StripeSubscriptionService:
    """
    Servicio para gestionar suscripciones de alquiler en Stripe.
    """
    
    @staticmethod
    def create_or_get_customer(tenant) -> str:
        """
        Crea un cliente en Stripe o retorna el ID existente.
        
        Args:
            tenant: Instancia del modelo Tenant
            
        Returns:
            str: ID del cliente en Stripe (cus_xxxxx)
        """
        # Si ya tiene un customer_id, retornarlo
        if tenant.stripe_customer_id:
            try:
                # Verificar que el customer existe en Stripe
                stripe.Customer.retrieve(tenant.stripe_customer_id)
                return tenant.stripe_customer_id
            except stripe.error.InvalidRequestError:
                logger.warning(f"Customer ID {tenant.stripe_customer_id} no válido, creando nuevo")
        
        # Crear nuevo customer en Stripe
        try:
            customer = stripe.Customer.create(
                email=tenant.email,
                name=tenant.name,
                phone=tenant.phone,
                metadata={
                    'tenant_id': tenant.id,
                    'tenant_name': tenant.name
                }
            )
            
            # Guardar el customer_id en la base de datos
            tenant.stripe_customer_id = customer.id
            tenant.save(update_fields=['stripe_customer_id'])
            
            logger.info(f"Cliente Stripe creado: {customer.id} para {tenant.email}")
            return customer.id
            
        except stripe.error.StripeError as e:
            logger.error(f"Error al crear customer en Stripe: {str(e)}")
            raise Exception(f"No se pudo crear el cliente en Stripe: {str(e)}")
    
    
    @staticmethod
    def create_price_for_property(property_obj) -> str:
        """
        Crea un Price (precio recurrente) en Stripe para la propiedad.
        
        Args:
            property_obj: Instancia del modelo Property
            
        Returns:
            str: ID del precio en Stripe (price_xxxxx)
        """
        try:
            # Convertir el monto a centavos (Stripe usa centavos)
            amount_cents = int(property_obj.monthly_rent * 100)
            
            price = stripe.Price.create(
                unit_amount=amount_cents,
                currency='usd',  # Cambiar según tu moneda
                recurring={
                    'interval': 'month',
                    'interval_count': 1
                },
                product_data={
                    'name': f'Alquiler - {property_obj.address}',
                    'metadata': {
                        'property_id': property_obj.id,
                        'address': property_obj.address
                    }
                }
            )
            
            logger.info(f"Price creado en Stripe: {price.id} para propiedad {property_obj.id}")
            return price.id
            
        except stripe.error.StripeError as e:
            logger.error(f"Error al crear price en Stripe: {str(e)}")
            raise Exception(f"No se pudo crear el precio en Stripe: {str(e)}")
    
    
    @staticmethod
    @transaction.atomic
    def create_subscription(agreement, payment_method_id: str) -> Dict[str, Any]:
        """
        Crea una suscripción en Stripe para un contrato de alquiler.
        
        FLUJO:
        1. Crear/obtener customer en Stripe
        2. Adjuntar método de pago al customer
        3. Crear price para la propiedad
        4. Crear subscription con el price
        5. Actualizar el Agreement con los IDs de Stripe
        
        Args:
            agreement: Instancia del modelo Agreement
            payment_method_id: ID del método de pago tokenizado desde el frontend (pm_xxxxx)
            
        Returns:
            dict: Información de la suscripción creada
        """
        try:
            # Paso 1: Crear o obtener customer
            customer_id = StripeSubscriptionService.create_or_get_customer(agreement.tenant)
            
            # Paso 2: Adjuntar el método de pago al customer
            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id
            )
            
            # Establecer como método de pago predeterminado
            stripe.Customer.modify(
                customer_id,
                invoice_settings={
                    'default_payment_method': payment_method_id
                }
            )
            
            # Paso 3: Crear price para la propiedad
            price_id = StripeSubscriptionService.create_price_for_property(agreement.property)
            
            # Paso 4: Crear la suscripción
            # Calcular el billing_cycle_anchor (día de cobro)
            billing_anchor = agreement.property.billing_day
            
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': price_id}],
                billing_cycle_anchor='now',  # O calcular según billing_day
                metadata={
                    'agreement_id': agreement.id,
                    'tenant_id': agreement.tenant.id,
                    'property_id': agreement.property.id
                },
                # Expandir para obtener el invoice más reciente
                expand=['latest_invoice.payment_intent']
            )
            
            # Paso 5: Actualizar el Agreement
            agreement.stripe_subscription_id = subscription.id
            agreement.stripe_price_id = price_id
            agreement.status = 'active'
            agreement.save(update_fields=['stripe_subscription_id', 'stripe_price_id', 'status'])
            
            logger.info(f"Suscripción creada: {subscription.id} para Agreement {agreement.id}")
            
            return {
                'success': True,
                'subscription_id': subscription.id,
                'status': subscription.status,
                'current_period_end': subscription.current_period_end
            }
            
        except stripe.error.CardError as e:
            # Error con la tarjeta
            logger.error(f"Error de tarjeta: {str(e)}")
            return {
                'success': False,
                'error': 'card_error',
                'message': str(e.user_message)
            }
        except stripe.error.StripeError as e:
            logger.error(f"Error de Stripe: {str(e)}")
            return {
                'success': False,
                'error': 'stripe_error',
                'message': str(e)
            }
        except Exception as e:
            logger.error(f"Error inesperado: {str(e)}")
            return {
                'success': False,
                'error': 'unexpected_error',
                'message': str(e)
            }
    
    
    @staticmethod
    def cancel_subscription(agreement) -> bool:
        """
        Cancela una suscripción en Stripe.
        
        Args:
            agreement: Instancia del modelo Agreement
            
        Returns:
            bool: True si se canceló exitosamente
        """
        if not agreement.stripe_subscription_id:
            logger.warning(f"Agreement {agreement.id} no tiene subscription_id")
            return False
        
        try:
            # Cancelar la suscripción al final del período actual
            subscription = stripe.Subscription.modify(
                agreement.stripe_subscription_id,
                cancel_at_period_end=True
            )
            
            agreement.status = 'cancelled'
            agreement.save(update_fields=['status'])
            
            logger.info(f"Suscripción {subscription.id} cancelada para Agreement {agreement.id}")
            return True
            
        except stripe.error.StripeError as e:
            logger.error(f"Error al cancelar suscripción: {str(e)}")
            return False


# =============================================================================
# PSEUDOCÓDIGO PARA WEBHOOK HANDLER
# =============================================================================

"""
ENDPOINT WEBHOOK DE STRIPE (views.py)

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse
import json

@csrf_exempt
@require_POST
def stripe_webhook(request):
    '''
    Endpoint para recibir eventos de Stripe mediante webhooks.
    
    IMPORTANTE: 
    - Debe estar en una URL pública accesible por Stripe
    - Configurar el webhook en el Dashboard de Stripe
    - Usar @csrf_exempt porque Stripe no envía CSRF token
    '''
    
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET  # Obtener del dashboard de Stripe
    
    try:
        # PASO 1: Verificar la firma del webhook (CRÍTICO PARA SEGURIDAD)
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        # Payload inválido
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        # Firma inválida
        return HttpResponse(status=400)
    
    # PASO 2: Procesar el evento según su tipo
    event_type = event['type']
    event_data = event['data']['object']
    
    # ===== EVENTOS DE FACTURA =====
    if event_type == 'invoice.payment_succeeded':
        '''
        Se disparó cuando un pago fue exitoso.
        '''
        subscription_id = event_data.get('subscription')
        amount_paid = event_data.get('amount_paid') / 100  # Convertir de centavos
        payment_intent_id = event_data.get('payment_intent')
        
        try:
            # Buscar el Agreement por subscription_id
            agreement = Agreement.objects.get(stripe_subscription_id=subscription_id)
            
            # Crear registro en PaymentHistory
            PaymentHistory.objects.create(
                agreement=agreement,
                amount=Decimal(str(amount_paid)),
                status='succeeded',
                stripe_payment_id=payment_intent_id,
            )
            
            # Asegurar que el Agreement esté activo
            if agreement.status != 'active':
                agreement.status = 'active'
                agreement.save(update_fields=['status'])
            
            logger.info(f"Pago exitoso registrado para Agreement {agreement.id}")
            
        except Agreement.DoesNotExist:
            logger.error(f"No se encontró Agreement con subscription_id: {subscription_id}")
    
    elif event_type == 'invoice.payment_failed':
        '''
        Se disparó cuando un pago falló.
        '''
        subscription_id = event_data.get('subscription')
        amount_due = event_data.get('amount_due') / 100
        payment_intent_id = event_data.get('payment_intent')
        
        try:
            agreement = Agreement.objects.get(stripe_subscription_id=subscription_id)
            
            # Crear registro de pago fallido
            PaymentHistory.objects.create(
                agreement=agreement,
                amount=Decimal(str(amount_due)),
                status='failed',
                stripe_payment_id=payment_intent_id or 'N/A',
                failure_reason='Payment failed - insufficient funds or card declined'
            )
            
            # Actualizar estado del Agreement
            agreement.status = 'past_due'
            agreement.save(update_fields=['status'])
            
            # OPCIONAL: Enviar notificación al inquilino
            # send_payment_failed_notification(agreement.tenant)
            
            logger.warning(f"Pago fallido para Agreement {agreement.id}")
            
        except Agreement.DoesNotExist:
            logger.error(f"No se encontró Agreement con subscription_id: {subscription_id}")
    
    # ===== EVENTOS DE SUSCRIPCIÓN =====
    elif event_type == 'customer.subscription.deleted':
        '''
        Se disparó cuando una suscripción fue cancelada o expiró.
        '''
        subscription_id = event_data.get('id')
        
        try:
            agreement = Agreement.objects.get(stripe_subscription_id=subscription_id)
            agreement.status = 'cancelled'
            agreement.save(update_fields=['status'])
            
            logger.info(f"Suscripción cancelada para Agreement {agreement.id}")
            
        except Agreement.DoesNotExist:
            logger.error(f"No se encontró Agreement con subscription_id: {subscription_id}")
    
    elif event_type == 'customer.subscription.updated':
        '''
        Se disparó cuando una suscripción fue actualizada (cambio de plan, etc).
        '''
        subscription_id = event_data.get('id')
        status = event_data.get('status')
        
        # Mapear estados de Stripe a estados del Agreement
        status_mapping = {
            'active': 'active',
            'past_due': 'past_due',
            'canceled': 'cancelled',
            'unpaid': 'past_due'
        }
        
        try:
            agreement = Agreement.objects.get(stripe_subscription_id=subscription_id)
            agreement.status = status_mapping.get(status, 'inactive')
            agreement.save(update_fields=['status'])
            
            logger.info(f"Suscripción actualizada para Agreement {agreement.id}")
            
        except Agreement.DoesNotExist:
            logger.error(f"No se encontró Agreement con subscription_id: {subscription_id}")
    
    # PASO 3: Retornar respuesta 200 OK a Stripe
    return JsonResponse({'status': 'success'}, status=200)
"""