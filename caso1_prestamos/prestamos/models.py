"""Modelos: Laboratorio, Equipo y Préstamo."""
from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import F, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone


class Laboratorio(models.Model):
    nombre = models.CharField("nombre", max_length=60, unique=True)
    ubicacion = models.CharField("ubicación", max_length=100, blank=True)

    class Meta:
        verbose_name = "laboratorio"
        verbose_name_plural = "laboratorios"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class EquipoQuerySet(models.QuerySet):
    def con_disponibilidad(self):
        """Agrega unidades prestadas y disponibles en UNA sola consulta (evita N+1)."""
        prestadas = Coalesce(
            Sum("prestamos__cantidad", filter=Q(prestamos__estado="activo")), 0
        )
        return self.annotate(
            unidades_prestadas=prestadas,
            unidades_disponibles=F("cantidad_total") - prestadas,
        )


class Equipo(models.Model):
    class Categoria(models.TextChoices):
        LAPTOP = "laptop", "Laptop"
        PROYECTOR = "proyector", "Proyector"
        CAMARA = "camara", "Cámara"
        ARDUINO = "arduino", "Kit Arduino"
        ROUTER = "router", "Router"
        SWITCH = "switch", "Switch"

    class Estado(models.TextChoices):
        OPERATIVO = "operativo", "Operativo"
        MANTENIMIENTO = "mantenimiento", "En mantenimiento"
        BAJA = "baja", "Dado de baja"

    codigo_patrimonial = models.CharField(
        "código patrimonial",
        max_length=20,
        unique=True,
        validators=[RegexValidator(r"^LAB-\d{4}$", "Formato válido: LAB-0001")],
    )
    nombre = models.CharField("nombre", max_length=80)
    marca = models.CharField("marca", max_length=50)
    modelo = models.CharField("modelo", max_length=50)
    categoria = models.CharField("categoría", max_length=20, choices=Categoria.choices)
    estado = models.CharField(
        "estado", max_length=20, choices=Estado.choices, default=Estado.OPERATIVO
    )
    laboratorio = models.ForeignKey(
        Laboratorio, on_delete=models.PROTECT, related_name="equipos",
        verbose_name="laboratorio",
    )
    cantidad_total = models.PositiveIntegerField(
        "unidades", default=1, validators=[MinValueValidator(1)]
    )
    fecha_ultimo_mantenimiento = models.DateField(
        "último mantenimiento", null=True, blank=True
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    objects = EquipoQuerySet.as_manager()

    class Meta:
        verbose_name = "equipo"
        verbose_name_plural = "equipos"
        ordering = ["codigo_patrimonial"]

    def __str__(self):
        return f"{self.codigo_patrimonial} - {self.nombre} ({self.get_estado_display()})"

    @property
    def cantidad_disponible(self):
        """Unidades libres. Usa la anotación si existe; si no, consulta."""
        if hasattr(self, "unidades_disponibles"):
            return self.unidades_disponibles
        prestadas = (
            self.prestamos.filter(estado=Prestamo.Estado.ACTIVO)
            .aggregate(total=Sum("cantidad"))["total"] or 0
        )
        return self.cantidad_total - prestadas

    @property
    def dias_desde_mantenimiento(self):
        if not self.fecha_ultimo_mantenimiento:
            return None
        return (timezone.localdate() - self.fecha_ultimo_mantenimiento).days

    @property
    def color_estado(self):
        """Clase de Bootstrap para pintar el estado."""
        return {
            self.Estado.OPERATIVO: "success",
            self.Estado.MANTENIMIENTO: "warning",
            self.Estado.BAJA: "secondary",
        }[self.estado]


class Prestamo(models.Model):
    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        DEVUELTO = "devuelto", "Devuelto"

    docente = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="prestamos", verbose_name="docente",
    )
    equipo = models.ForeignKey(
        Equipo, on_delete=models.PROTECT, related_name="prestamos", verbose_name="equipo"
    )
    cantidad = models.PositiveIntegerField(
        "cantidad", default=1, validators=[MinValueValidator(1)]
    )
    fecha_prestamo = models.DateField("fecha de préstamo", default=timezone.localdate)
    fecha_devolucion_prevista = models.DateField("devolución prevista")
    fecha_devolucion_real = models.DateField("devolución real", null=True, blank=True)
    estado = models.CharField(
        "estado", max_length=10, choices=Estado.choices, default=Estado.ACTIVO
    )
    observaciones = models.TextField("observaciones", blank=True)
    estado_retorno = models.CharField(
        "estado del equipo al retornar", max_length=20,
        choices=Equipo.Estado.choices, blank=True,
    )
    observaciones_devolucion = models.TextField("observaciones de devolución", blank=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="prestamos_registrados", verbose_name="registrado por",
    )
    recordatorio_enviado = models.BooleanField("recordatorio enviado", default=False)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "préstamo"
        verbose_name_plural = "préstamos"
        ordering = ["-fecha_prestamo", "-id"]
        permissions = [
            ("registrar_devolucion", "Puede registrar devoluciones"),
            ("ver_todos_los_prestamos", "Puede ver los préstamos de todos los docentes"),
        ]

    def __str__(self):
        return f"#{self.pk} {self.equipo.codigo_patrimonial} -> {self.docente.username}"

    @property
    def esta_vencido(self):
        return (
            self.estado == self.Estado.ACTIVO
            and self.fecha_devolucion_prevista < timezone.localdate()
        )

    @property
    def dias_retraso(self):
        """Días de retraso: hasta hoy si sigue activo, o hasta la devolución real."""
        fin = (
            timezone.localdate()
            if self.estado == self.Estado.ACTIVO
            else self.fecha_devolucion_real
        )
        if not fin:
            return 0
        return max(0, (fin - self.fecha_devolucion_prevista).days)

    def registrar_devolucion(self, fecha, estado_retorno, observaciones, usuario):
        """Cierra el préstamo y actualiza el estado del equipo si volvió con fallas."""
        self.fecha_devolucion_real = fecha
        self.estado = self.Estado.DEVUELTO
        self.estado_retorno = estado_retorno
        self.observaciones_devolucion = observaciones
        self.save()
        if estado_retorno != Equipo.Estado.OPERATIVO:
            self.equipo.estado = estado_retorno
            self.equipo.save(update_fields=["estado"])
