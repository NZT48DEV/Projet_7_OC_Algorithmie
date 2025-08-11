import csv
from pprint import pprint
import itertools

BUDGET_MAX = 500

def read_csv_columns(file_path):
    actions = []

    with open(file_path, 'r', encoding='utf-8-sig') as file:
        reader = csv.reader(file, delimiter=';')
        headers = next(reader)
        print(f"Colonnes : {headers}")

        for row in reader:
            action = row[0]
            cost = float(row[1].replace(",", "."))
            profit = float(row[2].replace(",", "."))
            actions.append((action, cost, profit))

    return actions

if __name__ == "__main__":
    # Code to execute if this script is run directly
    actions_list = read_csv_columns("actions.csv")
    pprint(actions_list)

    valid_combinations = []
    total_combinations = 0

    for r in range(1, len(actions_list) + 1):
        for combo in itertools.combinations(actions_list, r):
            total_combinations += 1
            total_cost = sum(action[1] for action in combo)
            total_profit = sum(action[1] * action[2] for action in combo)

            if total_cost <= BUDGET_MAX:
                valid_combinations.append((combo, total_cost, total_profit))

    print(f"\nNombre total de combinaisons possibles : {total_combinations}")
    print(f"Nombre de combinaisons valides (≤ {BUDGET_MAX}€) : {len(valid_combinations)}\n")

    valid_combinations.sort(key=lambda x: x[2], reverse=True)

    top_10 = valid_combinations[:10]

    print("Top 10 des combinaisons d'actions avec le meilleur bénéfice :")
    for rank, (combo, cost, profit) in enumerate(top_10, start=1):
        names = [action[0] for action in combo]
        pprint(f"{rank}. {names} | Coût: {cost} | Bénéfice: {profit:.2f}")
    