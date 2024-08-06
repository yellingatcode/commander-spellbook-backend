# Generated by Django 5.0.7 on 2024-08-06 08:39

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spellbook', '0030_resize_text_fields'),
    ]

    operations = [
        migrations.RenameField(
            model_name='variant',
            new_name='public_notes',
            old_name='notes',
        ),
        migrations.AlterField(
            model_name='variantsuggestion',
            name='status',
            field=models.CharField(choices=[('N', 'New'), ('NR', 'Needs Review'), ('RE', 'Ready'), ('A', 'Accepted'), ('R', 'Rejected')], default='N', help_text='Suggestion status for editors', max_length=2),
        ),
        migrations.AddField(
            model_name='variant',
            name='notes',
            field=models.TextField(blank=True, help_text='Notes about the combo', validators=[django.core.validators.RegexValidator(message='Unpaired double square brackets are not allowed.', regex='^(?:[^\\[]*(?:\\[(?!\\[)|\\[{2}[^\\[]+\\]{2}|\\[{3,}))*[^\\[]*$'), django.core.validators.RegexValidator(message='Symbols must be in the {1}{W}{U}{B}{R}{G}{B/P}{A}{E}{T}{Q}... format.', regex='^(?:[^\\{]*\\{(?:(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?|CHAOS|PW|TK|[WUBRG](?:\\/P)?|[1-9][0-9]{1,2}|H[WUBRG]|[0-9CPXYZSTQEA½∞])\\})*[^\\{]*$'), django.core.validators.RegexValidator(message='Only ordinary characters are allowed.', regex='^[\\x0A\\x0D\\x20-\\x7E\\x80\\x95\\x99\\xA1\\xA9\\xAE\\xB0\\xB1-\\xB3\\xBC-\\xFF]*$')]),
        ),
        migrations.AlterField(
            model_name='variant',
            name='public_notes',
            field=models.TextField(blank=True, help_text='Notes about the combo that will be displayed on the site', validators=[django.core.validators.RegexValidator(message='Unpaired double square brackets are not allowed.', regex='^(?:[^\\[]*(?:\\[(?!\\[)|\\[{2}[^\\[]+\\]{2}|\\[{3,}))*[^\\[]*$'), django.core.validators.RegexValidator(message='Symbols must be in the {1}{W}{U}{B}{R}{G}{B/P}{A}{E}{T}{Q}... format.', regex='^(?:[^\\{]*\\{(?:(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?|CHAOS|PW|TK|[WUBRG](?:\\/P)?|[1-9][0-9]{1,2}|H[WUBRG]|[0-9CPXYZSTQEA½∞])\\})*[^\\{]*$'), django.core.validators.RegexValidator(message='Only ordinary characters are allowed.', regex='^[\\x0A\\x0D\\x20-\\x7E\\x80\\x95\\x99\\xA1\\xA9\\xAE\\xB0\\xB1-\\xB3\\xBC-\\xFF]*$')]),
        ),
    ]
