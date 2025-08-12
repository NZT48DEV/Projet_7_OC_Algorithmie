import csv
import itertools
import time

BUDGET_MAX = 500
FILE_PATH = "actions.csv"


def load_csv(file_path, delimiter=";"):
    """
    Charge un fichier CSV et retourne les lignes (sans l'en-tête).
    Args:
        file_path (str): Chemin du fichier CSV.
        delimiter (str): Délimiteur de colonnes.
    Returns:
        list[list[str]]: Liste de lignes (chaque ligne est une liste de colonnes).
    """
    start = time.time()
    try:
        with open(file_path, "r", encoding="utf-8-sig") as file:
            reader = csv.reader(file, delimiter=delimiter)
            rows = list(reader)
    except FileNotFoundError:
        print(f"[ERREUR] Fichier introuvable : {file_path}")
        rows = []
    except Exception as e:
        print(f"[ERREUR] Problème lors de la lecture : {e}")
        rows = []
    elapsed = time.time() - start
    print(f"[Chrono] Lecture CSV : {elapsed:.4f} secondes")
    return rows


def parse_actions(rows):
    """
    Transforme les lignes CSV en liste de tuples (nom, coût, bénéfice).
    Remplace les virgules par des points pour les valeurs numériques.
    """
    start = time.time()
    actions = []
    for row in rows:
        try:
            action = row[0]
            cost = float(row[1].replace(",", "."))
            profit = float(row[2].replace(",", "."))
            actions.append((action, cost, profit))
        except (IndexError, ValueError) as e:
            print(f"[AVERTISSEMENT] Ligne ignorée {row} → {e}")
    elapsed = time.time() - start
    print(f"[Chrono] Parsing des données : {elapsed:.4f} secondes")
    return actions


def find_combinations(actions, budget):
    """
    Trouve toutes les combinaisons valides d'actions en respectant le budget.
    Args:
        actions (list[tuple]): Liste des actions (nom, coût, profit).
        budget (float): Budget maximum.

    Returns:
        list[tuple]: Liste de tuples (combo, coût total, bénéfice total).
    """
    start = time.time()
    valid_combinations = []
    total_combinations = 0

    for r in range(1, len(actions) + 1):
        for combo in itertools.combinations(actions, r):
            total_combinations += 1
            total_cost = sum(a[1] for a in combo)
            total_profit = sum(a[1] * a[2] for a in combo)

            if total_cost <= budget:
                valid_combinations.append((combo, total_cost, total_profit))

    elapsed = time.time() - start
    print(f"[Chrono] Génération des combinaisons : {elapsed:.4f} secondes")
    return valid_combinations, total_combinations


def display_top_combinations(combinations, limit=10):
    """
    Affiche les meilleures combinaisons triées par bénéfice décroissant.
    """
    start = time.time()
    combinations.sort(key=lambda x: x[2], reverse=True)
    top_combos = combinations[:limit]

    for rank, (combo, cost, profit) in enumerate(top_combos, start=1):
        names = [a[0] for a in combo]
        if limit == 1:
            print("\n[Meilleure combinaison d'actions] :")
        else:
            print(f"\n [Top {rank} des combinaisons d'actions] :")

        print(", ".join(names))
        print(f"[Coût] {cost:.2f}€")
        print(f"[Bénéfice] {profit:.2f}€")

    elapsed = time.time() - start
    print(f"\n[Chrono] Affichage du Top {limit} : {elapsed:.4f} secondes")


if __name__ == "__main__":
    global_start = time.time()

    rows = load_csv(FILE_PATH)
    actions_list = parse_actions(rows)
    valid_combos, total_combos = find_combinations(actions_list, BUDGET_MAX)

    print(f"\nNombre total de combinaisons possibles : {total_combos}")
    print(f"Nombre de combinaisons valides (<= {BUDGET_MAX}€) : {len(valid_combos)}")

    display_top_combinations(valid_combos, limit=10)

    global_elapsed = time.time() - global_start
    print(f"\n[Chrono GLOBAL] Durée totale d'exécution : {global_elapsed:.4f} secondes")
