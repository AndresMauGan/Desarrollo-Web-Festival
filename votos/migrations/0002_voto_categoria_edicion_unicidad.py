"""
Entrega 3 · RN-01 definida: un voto por usuario, categoría y edición.

1. Agrega Voto.categoria y Voto.edicion, primero opcionales.
2. Las llena en los votos que ya existan, tomándolas de su opción (opción → votación → categoría → edición).
3. Las vuelve obligatorias (lado «exactamente uno», PROTECT).
4. Crea la restricción única un_voto_por_usuario_categoria_edicion en MySQL.

Si una base ya tuviera dos votos del mismo usuario en la misma categoría y edición, el paso 4 falla:
la regla nueva no se puede aplicar sobre datos que ya la incumplen.
"""

import django.db.models.deletion
from django.db import migrations, models


def llenar_desde_la_opcion(apps, schema_editor):
    # El modelo histórico usa un manager normal, así que update() funciona aquí (no aplica VotoQuerySet).
    Voto = apps.get_model("votos", "Voto")
    for voto in Voto.objects.select_related("opcion__votacion__categoria"):
        categoria = voto.opcion.votacion.categoria
        Voto.objects.filter(pk=voto.pk).update(
            votacion_id=voto.opcion.votacion_id, categoria_id=categoria.pk, edicion_id=categoria.edicion_id
        )


class Migration(migrations.Migration):

    dependencies = [
        ("festival", "0001_initial"),
        ("votos", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="voto",
            name="categoria",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="votos",
                                    to="festival.categoria", verbose_name="categoría"),
        ),
        migrations.AddField(
            model_name="voto",
            name="edicion",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="votos",
                                    to="festival.edicion", verbose_name="edición"),
        ),
        migrations.RunPython(llenar_desde_la_opcion, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="voto",
            name="categoria",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="votos",
                                    to="festival.categoria", verbose_name="categoría"),
        ),
        migrations.AlterField(
            model_name="voto",
            name="edicion",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="votos",
                                    to="festival.edicion", verbose_name="edición"),
        ),
        migrations.AlterField(
            model_name="voto",
            name="huella_ip",
            field=models.CharField(help_text="HMAC-SHA256 de la IP; la IP no se guarda en claro.", max_length=64, verbose_name="huella de IP"),
        ),
        migrations.AlterField(
            model_name="voto",
            name="huella_navegador",
            field=models.CharField(help_text="HMAC-SHA256 del navegador (User-Agent).", max_length=64, verbose_name="huella del navegador"),
        ),
        migrations.AddConstraint(
            model_name="voto",
            constraint=models.UniqueConstraint(fields=("usuario", "categoria", "edicion"), name="un_voto_por_usuario_categoria_edicion"),
        ),
    ]
