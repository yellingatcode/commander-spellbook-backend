# Generated by Django 4.1.7 on 2023-04-16 14:55

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spellbook', '0005_remove_cardincombo_zone_location_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='combo',
            name='mana_needed',
            field=models.CharField(blank=True, default='', help_text='Mana needed for this combo. Use the {1}{W}{U}{B}{R}{G}{B/P}... format.', max_length=200, validators=[django.core.validators.RegexValidator(message='Mana needed must be in the {1}{W}{U}{B}{R}{G}{B/P}... format, and must start with mana symbols, but can contain normal text later.', regex='^(?:(?:\\{(?:[WUBRG](?:\\/P)?|[0-9CPXYZS∞]|[1-9][0-9]{1,2}|(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\})[^\\{\\}\\[\\]]*)*$')]),
        ),
        migrations.AlterField(
            model_name='template',
            name='scryfall_query',
            field=models.CharField(help_text='Variables supported: manavalue, mv, power, pow, toughness, tou, powtou, pt, loyalty, loy, color, c, identity, id, has, type, t, keyword, is, mana, m, devotion, produces. Operators supported: =, !=, <, >, <=, >=, :. You can compose a "and"/"or" expression made of "and"/"or" expressions, like "(c:W or c:U) and (t:creature or t:artifact)". You can also omit parentheses when not necessary, like "(c:W or c:U) t:creature". More info at: https://scryfall.com/docs/syntax.', max_length=255, validators=[django.core.validators.RegexValidator(message='Invalid Scryfall query syntax.', regex='^(?:(?:\\((?:(?:-?(?:(?:(?:c|color|id|identity|produces)(?::|[<>]=?|!=|=)|(?:has|t|type|keyword|is):)(?:[^\\s:<>!="]+|"[^"]+")|(?:m|mana|devotion)(?::|[<>]=?|!=|=)(?:\\{(?:[WUBRG](?:\\/P)?|[0-9CPXYZS∞]|[1-9][0-9]{1,2}|(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\})+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy)(?::|[<>]=?|!=|=)(?:\\d+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy))))(?: (?:and |or )?(?:-?(?:(?:(?:c|color|id|identity|produces)(?::|[<>]=?|!=|=)|(?:has|t|type|keyword|is):)(?:[^\\s:<>!="]+|"[^"]+")|(?:m|mana|devotion)(?::|[<>]=?|!=|=)(?:\\{(?:[WUBRG](?:\\/P)?|[0-9CPXYZS∞]|[1-9][0-9]{1,2}|(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\})+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy)(?::|[<>]=?|!=|=)(?:\\d+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy)))))*)\\)|(?:(?:-?(?:(?:(?:c|color|id|identity|produces)(?::|[<>]=?|!=|=)|(?:has|t|type|keyword|is):)(?:[^\\s:<>!="]+|"[^"]+")|(?:m|mana|devotion)(?::|[<>]=?|!=|=)(?:\\{(?:[WUBRG](?:\\/P)?|[0-9CPXYZS∞]|[1-9][0-9]{1,2}|(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\})+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy)(?::|[<>]=?|!=|=)(?:\\d+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy))))(?: (?:and |or )?(?:-?(?:(?:(?:c|color|id|identity|produces)(?::|[<>]=?|!=|=)|(?:has|t|type|keyword|is):)(?:[^\\s:<>!="]+|"[^"]+")|(?:m|mana|devotion)(?::|[<>]=?|!=|=)(?:\\{(?:[WUBRG](?:\\/P)?|[0-9CPXYZS∞]|[1-9][0-9]{1,2}|(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\})+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy)(?::|[<>]=?|!=|=)(?:\\d+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy)))))*))(?: (?:and |or )?(?:\\((?:(?:-?(?:(?:(?:c|color|id|identity|produces)(?::|[<>]=?|!=|=)|(?:has|t|type|keyword|is):)(?:[^\\s:<>!="]+|"[^"]+")|(?:m|mana|devotion)(?::|[<>]=?|!=|=)(?:\\{(?:[WUBRG](?:\\/P)?|[0-9CPXYZS∞]|[1-9][0-9]{1,2}|(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\})+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy)(?::|[<>]=?|!=|=)(?:\\d+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy))))(?: (?:and |or )?(?:-?(?:(?:(?:c|color|id|identity|produces)(?::|[<>]=?|!=|=)|(?:has|t|type|keyword|is):)(?:[^\\s:<>!="]+|"[^"]+")|(?:m|mana|devotion)(?::|[<>]=?|!=|=)(?:\\{(?:[WUBRG](?:\\/P)?|[0-9CPXYZS∞]|[1-9][0-9]{1,2}|(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\})+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy)(?::|[<>]=?|!=|=)(?:\\d+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy)))))*)\\)|(?:(?:-?(?:(?:(?:c|color|id|identity|produces)(?::|[<>]=?|!=|=)|(?:has|t|type|keyword|is):)(?:[^\\s:<>!="]+|"[^"]+")|(?:m|mana|devotion)(?::|[<>]=?|!=|=)(?:\\{(?:[WUBRG](?:\\/P)?|[0-9CPXYZS∞]|[1-9][0-9]{1,2}|(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\})+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy)(?::|[<>]=?|!=|=)(?:\\d+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy))))(?: (?:and |or )?(?:-?(?:(?:(?:c|color|id|identity|produces)(?::|[<>]=?|!=|=)|(?:has|t|type|keyword|is):)(?:[^\\s:<>!="]+|"[^"]+")|(?:m|mana|devotion)(?::|[<>]=?|!=|=)(?:\\{(?:[WUBRG](?:\\/P)?|[0-9CPXYZS∞]|[1-9][0-9]{1,2}|(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\})+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy)(?::|[<>]=?|!=|=)(?:\\d+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy)))))*)))*)$')], verbose_name='Scryfall query'),
        ),
        migrations.AlterField(
            model_name='variant',
            name='mana_needed',
            field=models.CharField(blank=True, default='', help_text='Mana needed for this combo. Use the {1}{W}{U}{B}{R}{G}{B/P}... format.', max_length=200, validators=[django.core.validators.RegexValidator(message='Mana needed must be in the {1}{W}{U}{B}{R}{G}{B/P}... format, and must start with mana symbols, but can contain normal text later.', regex='^(?:(?:\\{(?:[WUBRG](?:\\/P)?|[0-9CPXYZS∞]|[1-9][0-9]{1,2}|(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\})[^\\{\\}\\[\\]]*)*$')]),
        ),
    ]