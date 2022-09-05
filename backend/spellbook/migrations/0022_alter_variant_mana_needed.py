# Generated by Django 4.1 on 2022-09-05 16:17

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spellbook', '0021_alter_combo_cards_state_alter_combo_mana_needed_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='variant',
            name='mana_needed',
            field=models.CharField(blank=True, default='', help_text='Mana needed for this combo. Use the {1}{W}{U}{B}{R}{G} format.', max_length=50, validators=[django.core.validators.RegexValidator(message='Mana needed must be in the {1}{W}{U}{B}{R}{G} format.', regex='^(?:\\{(?:[0-9WUBRGCXS]|1[0-6])(?:\\/[WUBRG])?(?:\\/[WUBRGP])?\\})*$')]),
        ),
    ]
