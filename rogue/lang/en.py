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
        ("Esc", "quit"),
    ]