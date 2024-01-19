from django.core.validators import RegexValidator, MinLengthValidator

FIRST_CAPITAL_LETTER_REGEX = r'^[A-Z]'
FIRST_CAPITAL_LETTER_VALIDATOR = RegexValidator(regex=FIRST_CAPITAL_LETTER_REGEX, message='Must start with a capital letter.')

NO_TRAILING_PUNCTUATION_REGEX = r'[A-Za-z0-9()\{\}]$'
NO_TRAILING_PUNCTUATION_VALIDATOR = RegexValidator(regex=NO_TRAILING_PUNCTUATION_REGEX, message='Must not end with punctuation.')

MANA_SYMBOL = r'(?:[WUBRG](?:\/P)?|[0-9CPXYZS∞]|[1-9][0-9]{1,2}|(?:2\/[WUBRG]|W\/U|W\/B|U\/B|U\/R|B\/R|B\/G|R\/G|R\/W|G\/W|G\/U)(?:\/P)?)'
MANA_REGEX = r'^(?:(?:\{' + MANA_SYMBOL + r'\})[^\{\}\[\]]*)*$'
MANA_VALIDATOR = RegexValidator(regex=MANA_REGEX, message='Mana needed must be in the {1}{W}{U}{B}{R}{G}{B/P}... format, and must start with mana symbols, but can contain normal text later.')

DOUBLE_SQUARE_BRACKET_TEXT_REGEX = r'^(?:[^\[]*(?:\[(?!\[)|\[{2}[^\[]+\]{2}|\[{3,}))*[^\[]*$'
DOUBLE_SQUARE_BRACKET_TEXT_VALIDATOR = RegexValidator(regex=DOUBLE_SQUARE_BRACKET_TEXT_REGEX, message='Unpaired double square brackets are not allowed.')

ORACLE_SYMBOL = r'(?:(?:2\/[WUBRG]|W\/U|W\/B|B\/R|B\/G|U\/B|U\/R|R\/G|R\/W|G\/W|G\/U)(?:\/P)?|CHAOS|PW|TK|[WUBRG](?:\/P)?|[1-9][0-9]{1,2}|H[WUBRG]|[0-9CPXYZSTQEA½∞])'
SYMBOLS_TEXT_REGEX = r'^(?:[^\{]*\{' + ORACLE_SYMBOL + r'\})*[^\{]*$'
SYMBOLS_TEXT_VALIDATOR = RegexValidator(regex=SYMBOLS_TEXT_REGEX, message='Symbols must be in the {1}{W}{U}{B}{R}{G}{B/P}{A}{E}{T}{Q}... format.')

ORDINARY_CHARACTERS_REGEX = r'^[\x0A\x0D\x20-\x7E\x80\x95\x99\xA1\xA9\xAE\xB0\xB1-\xB3\xBC-\xFF]*$'
ORDINARY_CHARACTERS_VALIDATOR = RegexValidator(regex=ORDINARY_CHARACTERS_REGEX, message='Only ordinary characters are allowed.')

TEXT_VALIDATORS = [DOUBLE_SQUARE_BRACKET_TEXT_VALIDATOR, SYMBOLS_TEXT_VALIDATOR, ORDINARY_CHARACTERS_VALIDATOR]
NAME_VALIDATORS = [FIRST_CAPITAL_LETTER_VALIDATOR, NO_TRAILING_PUNCTUATION_VALIDATOR, *TEXT_VALIDATORS]

IDENTITY_REGEX = r'^(?:W?U?B?R?G?|C)$'
IDENTITY_VALIDATORS = [RegexValidator(regex=IDENTITY_REGEX, message='Can be any combination of one or more letters in [W,U,B,R,G], in order, otherwise C for colorless.'), MinLengthValidator(1)]

# Scryfall query syntax: https://scryfall.com/docs/syntax
COMPARISON_OPERATORS = r'(?::|[<>]=?|!=|=)'
NUMERIC_VARIABLE = r'(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy)'
STRING_COMPARABLE_VARIABLE = r'(?:c|color|id|identity|produces)'
STRING_UNCOMPARABLE_VARIABLE = r'(?:has|t|type|keyword|is)'
MANA_COMPARABLE_VARIABLE = r'(?:m|mana|devotion)'
SCRYFALL_QUERY_ATOM = r'(?:-?(?:' + \
    r'(?:' + STRING_COMPARABLE_VARIABLE + COMPARISON_OPERATORS + r'|' + STRING_UNCOMPARABLE_VARIABLE + r':)(?:[^\s:<>!="]+|"[^"]+")|' + \
    MANA_COMPARABLE_VARIABLE + COMPARISON_OPERATORS + r'(?:\{' + MANA_SYMBOL + r'\})+|' + \
    NUMERIC_VARIABLE + COMPARISON_OPERATORS + r'(?:\d+|' + NUMERIC_VARIABLE + r')' + \
    r'))'
SCRYFALL_EXPRESSION = r'(?:' + SCRYFALL_QUERY_ATOM + r'(?: (?:and |or )?' + SCRYFALL_QUERY_ATOM + r')*)'
SCRYFALL_EXPRESSION_BRACKETS = r'(?:\(' + SCRYFALL_EXPRESSION + r'\)|' + SCRYFALL_EXPRESSION + r')'
SCRYFALL_QUERY_REGEX = r'^(?:' + SCRYFALL_EXPRESSION_BRACKETS + r'(?: (?:and |or )?' + SCRYFALL_EXPRESSION_BRACKETS + r')*)$'
SCRYFALL_QUERY_VALIDATOR = RegexValidator(regex=SCRYFALL_QUERY_REGEX, message='Invalid Scryfall query syntax.')
SCRYFALL_QUERY_HELP = 'Variables supported: manavalue, mv, power, pow, toughness, tou, powtou, pt, loyalty, loy, color, c, identity, id, has, type, t, keyword, is, mana, m, devotion, produces. Operators supported: =, !=, <, >, <=, >=, :. You can compose a "and"/"or" expression made of "and"/"or" expressions, like "(c:W or c:U) and (t:creature or t:artifact)". You can also omit parentheses when not necessary, like "(c:W or c:U) t:creature". More info at: https://scryfall.com/docs/syntax.'
