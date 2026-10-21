/** Original UGA fixture. Static analysis only; no Android or game process is launched. */
public final class CombatRules {
    public static int clampHp(int hp) {
        return Math.max(0, Math.min(100, hp));
    }

    public static int applyDamage(int hp, int damage) {
        return clampHp(hp - Math.max(0, damage));
    }

    public static int usePotion(int hp) {
        return clampHp(hp + 30);
    }
}
