/* Original UGA fixture. Compile and statically analyze; never execute the sample. */
int clamp_hp(int hp) {
    if (hp < 0) return 0;
    if (hp > 100) return 100;
    return hp;
}

int apply_damage(int hp, int damage) {
    return clamp_hp(hp - (damage < 0 ? 0 : damage));
}

int use_potion(int hp) {
    return clamp_hp(hp + 30);
}

int main(void) {
    return apply_damage(100, 20) == 80 && use_potion(80) == 100 ? 0 : 1;
}
