import itertools

BUDGET_MAX = 167

actions = [
    ("Action-1", 37, 0.07),
    ("Action-2", 54, 0.11),
    ("Action-3", 78, 0.14),
    ("Action-4", 111, 0.21)
]

valid_combinations = []

for r in range(1, len(actions) + 1):
    for combo in itertools.combinations(actions, r):
        total_cost = sum(action[1] for action in combo)
        total_profit = sum(action[1] * action[2] for action in combo)

        if total_cost <= BUDGET_MAX:
            valid_combinations.append((combo, total_cost, total_profit))

valid_combinations.sort(key=lambda x: x[2], reverse=True)

top_3 = valid_combinations[:3]

print("Top 3 des combinaisons d'actions avec le meilleur bénéfice :")
for rank, (combo, cost, profit) in enumerate(top_3, start=1):
    names = [action[0] for action in combo]
    print(f"{rank}. {names} | Coût: {cost} | Bénéfice: {profit:.2f}")