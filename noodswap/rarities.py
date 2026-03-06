RARITY_WEIGHTS = {
    "common": 198,
    "uncommon": 112,
    "rare": 62,
    "epic": 33,
    "legendary": 17,
    "mythic": 8,
    "divine": 3,
    "celestial": 1,
}

# rarity weight calculations:
#
# f(1)            = 1
# ceil(1  *1.7+1) = 3
# ceil(3  *1.7+2) = 8
# ceil(8  *1.7+3) = 17
# ceil(17 *1.7+4) = 33
# ceil(33 *1.7+5) = 62
# ceil(62 *1.7+6) = 112
# ceil(112*1.7+7) = 198
#
# (198+112+62+33+17+8+3+1)/3 = 144.67, so every 145 pulls,
# someone can expect to see a celestial. therefore, a celestial
# should be worth about 145x an average card. so, roughly, in
# the range 200-400.
