SPAWN_NAMES = {
    'monster_names' : ['Rat', 'Goblin', 'Brute', 'Ogre', 'Horror'],
    'player_name' : 'You',
    'portal_name' : 'portal',
    'stairs_name' : 'stairs down',
    'merchant_name' : 'Merchant',
    'remains' : 'remains of',
}

STATS = {
    'hp' : 'Max HP',
    'dm' : 'Damage',
    'df' : 'Defense' ,
    'at' : 'Atk Range',
    'cr' : 'Crit',
    'dg' : 'Dodge',
    'vw' : 'View',
    'hl' : 'Heal',
    'gl' : 'Gold',
}

ADJECTIVES = [
    'Rusty', 'Gleaming', 'Ancient', 'Cursed', 'Blessed', 'Jagged', 'Twisted',
    'Runed', 'Feral', 'Ethereal', 'Vicious', 'Humming', 'Frostbitten', 'Charred',
    'Gilded', 'Ravenous', 'Whispering', 'Fabled', 'Wretched', 'Storied',
]

NOUNS = [
    'Stick', 'Branch', 'Cudgel', 'Rod', 'Stave', 'Splinter', 'Baton', 'Switch',
    'Bough', 'Shard', 'Talon', 'Fang', 'Sliver', 'Wand', 'Cane',
]

LOG_MESSAGES = {
    'init' : 'You descend into the dungeon.',
    'portal' : 'You step through a shimmering portal.',
    'descend' : ['You descend to depth' , 'The monsters here are stronger.'],
    'equip' : 'You ready the ',
    'unequip' : 'You stow the ',
    'limit' : 'You can only use two items at once.',
    'shop' : 'The merchant lays out their wares.',
    'no_gold' : 'Not enough gold.',
    'upgrade' : ['Upgraded', 'for', 'g.'],
    'sold' : ['Sold', 'for', 'g.'],
    'kill' : ['You die!', 'dies.'],
    'loot' : ['You loot the', 'Your pack is full; the loot is lost.']
}

UI_LABELS = {
    'die' : "You have died.  Press ESC to quit.",
    'depth' : "Depth",
    'gold' : STATS['gl'],
    'kills' : 'Kills',
    'items' : 'Items',
    'using' : 'Using',
    'scouting' : '[Scouting]',
    'hp' : 'HP',
    'inv' : " Inventory ",
    'empty' : "(empty - kill monsters for loot)",
    'character' : "Character",
    'inv_hints' : "up/down move  Enter equip  i/Esc close",
    'merch_title' : 'Merchant - Gold:',
    'upgrade_title' : "Buy permanent upgrades:",
    'upgrade_row' : 'g   owned ',
    'sell_title' : " Sell items ",
    'sell_nothing' : "(nothing to sell)",
    'merch_hints' : "up/down move  Enter buy/sell  Esc close",
}

ACTIONS = {
    'heal' : ['You tend your wounds (+', ' HP).', "You are already at full health."],
    'scout' : "You scan the surroundings.",
    'blocked' : "The way is blocked.",
    'hit' : ["hit", "hits"],
    'dodge' : ["dodge", "dodges", 'the blow.'],
    'dmg' : [' (crit!)', 'for', 'but deal no damage.']
}

CONTROL_HINTS = [
        ("move", "arrows/numpad/qweadzxc"),
        ("s", "wait"),
        ("r", "heal"),
        ("f", "scout"),
        ("i", "inventory"),
        ("Esc", "menu"),
    ]

MENU = {
    'title' : 'PROCGEN ROGUE',
    'play' : 'Play',
    'continue' : 'Continue',
    'tutorial' : 'Tutorial',
    'language' : 'Language',
    'lang_name' : 'English',
    'exit' : 'Exit',
    'hints' : 'up/down move   Enter select   Esc exit',
    'generating' : 'Generating cave...',
}

TUTORIAL = {
    'welcome' : 'Welcome to the tutorial.',
    'help' : [
        "HOW TO PLAY",
        "",
        "Move with the arrow keys, the numpad,",
        "or the Q W E / A D / Z X C cluster.",
        "S or .  waits a turn.",
        "",
        "Walk into a monster to fight it: any",
        "enemy within your attack range is",
        "struck automatically every turn.",
        "",
        "r   heal a little HP (an activity -",
        "    you won't attack that turn)",
        "f   scout: see further until you move",
        "i   inventory and character sheet",
        "",
        "Kill the rats, loot them, then open",
        "the inventory (i) and press Enter to",
        "equip an item.",
        "",
        "Esc  return to the main menu.",
    ],
}