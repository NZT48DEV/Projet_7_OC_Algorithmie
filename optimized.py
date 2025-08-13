import csv
import time
import math
from typing import List, Tuple, Optional
import multiprocessing as mp

# -----------------------------
# Paramètres
# -----------------------------
FILE_PATH = "dataset_1.csv"
ENCODING = "utf-8-sig"
BUDGET_MAX = 500.0  # en euros

MIN_STEP_CENTS = 100
MAX_STEP_CENTS = 2000

# -----------------------------
# Config
# -----------------------------
DEBUG_MODE = False
USE_PRE_FILTER = True
RATIO_MIN_RELATIVE = 0.05


def debug_print(*args, **kwargs) -> None:
    """
    Affiche des messages de debug uniquement si DEBUG_MODE est True.
    """
    if DEBUG_MODE:
        print(*args, **kwargs)


# -----------------------------
# Lecture CSV + détection
# -----------------------------
def load_csv_and_detect(file_path: str) -> Tuple[List[List[str]], str]:
    """
    Lit un fichier CSV en détectant le délimiteur et le format de bénéfice.

    Args:
        file_path: Chemin vers le fichier CSV.

    Returns:
        (rows, profit_format) où :
        - rows est une liste de lignes (liste de cellules str),
        - profit_format vaut "percent" si la 3e colonne est majoritairement exprimée en pourcentage,
          sinon "decimal".
    """
    with open(file_path, "r", encoding=ENCODING) as f:
        sample = f.read(1024)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";, \t")
            delim = dialect.delimiter
        except Exception:
            delim = ";"
        f.seek(0)
        reader = csv.reader(f, delimiter=delim)
        rows = list(reader)

    profit_format = detect_profit_format_from_rows(rows)
    debug_print(f"[DEBUG] Délimiteur détecté : '{delim}'")
    debug_print(f"[DEBUG] Format bénéfices   : {profit_format}")
    debug_print(f"[DEBUG] Lignes lues        : {len(rows)}")
    return rows, profit_format


# -----------------------------
# Détection format bénéfice
# -----------------------------
def detect_profit_format_from_rows(rows: List[List[str]]) -> str:
    """
    Détermine si la colonne 'bénéfice' (colonne 3) est un pourcentage ou un décimal.

    Heuristique :
    - On collecte les valeurs numériques de la 3e colonne.
    - Si la majorité des valeurs > 1.0, on considère qu'elles sont en pourcentage.
      (ex. 15 => 15%, 20 => 20%)
    - Sinon, on considère un ratio décimal (ex. 0.15 => 15%).

    Args:
        rows: Lignes du CSV (en incluant l'entête potentielle).

    Returns:
        "percent" ou "decimal".
    """
    values = []
    for i, row in enumerate(rows):
        if i == 0 or len(row) < 3:
            continue
        try:
            val = float(row[2].strip().replace(",", "."))
            values.append(val)
        except ValueError:
            continue
    if not values:
        return "percent"
    percent_count = sum(1 for v in values if v > 1.0)
    return "percent" if percent_count >= len(values) / 2 else "decimal"


# -----------------------------
# Nettoyage & conversion
# -----------------------------
def clean_row(row: List[str]) -> List[str]:
    """
    Nettoie une ligne (trim + remplace la virgule par un point).

    Args:
        row: Liste de cellules brutes.

    Returns:
        Ligne nettoyée.
    """
    return [cell.strip().replace(",", ".") for cell in row]


def convert_values(
    name_str: str, cost_str: str, profit_str: str, profit_format: str
) -> Optional[Tuple[str, float, float]]:
    """
    Convertit les champs bruts en valeurs exploitables.

    Args:
        name_str: Nom de l'action/option.
        cost_str: Coût (peut contenir des virgules).
        profit_str: Bénéfice/rendement (pourcentage ou ratio).
        profit_format: "percent" pour interpréter profit_str comme un pourcentage,
                       "decimal" pour un ratio.

    Returns:
        (name, cost, rate) ou None si conversion impossible/invalides.
    """
    try:
        cost = float(cost_str.replace(",", "."))
    except ValueError:
        return None
    if cost <= 0:
        return None

    try:
        profit_val = float(profit_str.replace(",", "."))
    except ValueError:
        return None

    rate = (profit_val / 100.0) if profit_format == "percent" else profit_val
    if rate <= 0:
        return None

    return name_str.strip(), cost, rate


def parse_actions(rows: List[List[str]], profit_format: str) -> List[Tuple[str, float, float]]:
    """
    Transforme les lignes CSV en une liste d'actions valides.

    Args:
        rows: Lignes du CSV.
        profit_format: "percent" ou "decimal".

    Returns:
        Liste d'actions sous forme (name, cost, rate).
    """
    actions: List[Tuple[str, float, float]] = []
    for i, row in enumerate(rows):
        row = clean_row(row)
        if i == 0:
            continue  # ignore l'entête
        if len(row) < 3:
            continue
        converted = convert_values(row[0], row[1], row[2], profit_format)
        if converted:
            actions.append(converted)
    return actions


# -----------------------------
# Pré-filtrage
# -----------------------------
def pre_filter_actions(actions: List[Tuple[str, float, float]]) -> List[Tuple[str, float, float]]:
    """
    Filtre simple pour éliminer les actions non viables (coût/rate <= 0) ou
    avec un ratio en dessous d'un seuil minimal relatif.

    Args:
        actions: Liste d'actions (name, cost, rate).

    Returns:
        Liste filtrée.
    """
    if not USE_PRE_FILTER:
        return actions

    filtered: List[Tuple[str, float, float]] = []
    for (n, c, r) in actions:
        if c <= 0 or r <= 0:
            continue
        if r < RATIO_MIN_RELATIVE:
            continue
        filtered.append((n, c, r))
    return filtered


# -----------------------------
# Utilitaires sac à dos 0/1
# -----------------------------
def prune_over_budget(
    actions: List[Tuple[str, float, float]], budget: float
) -> List[Tuple[str, float, float]]:
    """
    Écarte les actions dont le coût dépasse le budget.

    Args:
        actions: Liste (name, cost, rate).
        budget: Budget max en euros.

    Returns:
        Liste filtrée.
    """
    return [(n, c, r) for (n, c, r) in actions if c <= budget]


def dedupe_same_cost_keep_best_rate(
    actions: List[Tuple[str, float, float]]
) -> List[Tuple[str, float, float]]:
    """
    Déduplique sur la base du coût (en centimes), en conservant le meilleur taux.

    Args:
        actions: Liste (name, cost, rate).

    Returns:
        Liste dédupliquée.
    """
    by_cost = {}
    for n, c, r in actions:
        key = int(round(c * 100))
        if key not in by_cost or r > by_cost[key][2]:
            by_cost[key] = (n, c, r)
    return list(by_cost.values())


def prune_exact(
    actions: List[Tuple[str, float, float]], budget: float
) -> List[Tuple[str, float, float]]:
    """
    Filtrage exact avant DP : enlève > budget + déduplique par coût.

    Args:
        actions: Liste (name, cost, rate).
        budget: Budget en euros.

    Returns:
        Liste nettoyée.
    """
    a = prune_over_budget(actions, budget)
    a = dedupe_same_cost_keep_best_rate(a)
    return a


# -----------------------------
# DP parallèle par granularité (step)
# -----------------------------
def _dp_for_step(args: Tuple[List[Tuple[str, float, float]], float, int]):
    """
    Routine DP pour une granularité donnée (step), compatible multiprocessing.

    Args:
        args: Tuple (actions, budget_eur, step) où :
            - actions: liste (name, cost, rate),
            - budget_eur: budget en euros,
            - step: granularité en centimes (taille d'unité pour le DP).

    Returns:
        (chosen, total_cost_eur, max_profit_eur, meta) ou None si timeout interne.
        - chosen: liste des actions choisies,
        - total_cost_eur: coût total,
        - max_profit_eur: bénéfice total,
        - meta: dict {"algo": "dp", "step": step}.
    """
    actions, budget_eur, step = args
    costs_cents = [int(round(c * 100)) for (_, c, _) in actions]
    profits_eur = [c * r for (_, c, r) in actions]
    budget_cents = int(round(budget_eur * 100))

    start_time = time.time()
    costs_u = [(c + step - 1) // step for c in costs_cents]
    B = budget_cents // step

    best = [-1.0] * (B + 1)
    parent = [None] * (B + 1)
    best[0] = 0.0

    for idx, cu in enumerate(costs_u):
        p = profits_eur[idx]
        for w in range(B, cu - 1, -1):
            bw_cu = best[w - cu]
            if bw_cu >= 0.0:
                cand = bw_cu + p
                if cand > best[w]:
                    best[w] = cand
                    parent[w] = (w - cu, idx)

    # Garde-fou temps (identique au code initial)
    elapsed = time.time() - start_time
    if elapsed >= 1.0:
        return None

    w_star = max(range(B + 1), key=lambda w: (best[w], w))
    max_profit = best[w_star]
    if max_profit < 0:
        return None

    # Reconstruit la solution
    chosen_idx = set()
    w = w_star
    while w > 0 and parent[w] is not None:
        prev_w, idx = parent[w]
        if prev_w == w:
            break
        chosen_idx.add(idx)
        w = prev_w

    chosen = []
    total_cost_eur = 0.0
    for i, (name, cost_eur, rate) in enumerate(actions):
        if i in chosen_idx:
            chosen.append((name, cost_eur, rate))
            total_cost_eur += cost_eur

    # Greedy sur budget résiduel (identique à l'implémentation d'origine)
    remaining_budget = budget_eur - total_cost_eur
    if remaining_budget > 1e-9:
        remaining = [
            (i, actions[i]) for i in range(len(actions))
            if i not in chosen_idx and actions[i][1] > 0 and actions[i][2] > 0
        ]
        remaining.sort(key=lambda t: (-t[1][2], t[1][1]))
        for i, (name, c, r) in remaining:
            if c <= remaining_budget + 1e-9:
                chosen.append((name, c, r))
                total_cost_eur += c
                max_profit += c * r
                remaining_budget = budget_eur - total_cost_eur
                if remaining_budget <= 1e-9:
                    break

    return chosen, total_cost_eur, max_profit, {"algo": "dp", "step": step}


def knapsack_dp_auto(
    actions: List[Tuple[str, float, float]],
    budget_eur: float,
    time_limit: float = 0.82
) -> Tuple[List[Tuple[str, float, float]], float, float, dict]:
    """
    Cherche automatiquement une bonne granularité (step) en centimes pour la DP,
    lance les variantes en parallèle et retient la meilleure solution (puis la plus fine
    en cas d'égalité).

    Args:
        actions: Liste (name, cost, rate).
        budget_eur: Budget total en euros.
        time_limit: Limite temps globale pour l'exploration des steps.

    Returns:
        (chosen, total_cost, total_profit, meta) :
        - chosen: liste d'actions sélectionnées,
        - total_cost: coût total en euros,
        - total_profit: bénéfice total en euros,
        - meta: dict {"algo": "dp", "step": step_retenu}.
    """
    actions = prune_exact(actions, budget_eur)
    if not actions:
        return [], 0.0, 0.0, {"algo": "dp", "step": MIN_STEP_CENTS}

    costs_cents = [int(round(c * 100)) for (_, c, _) in actions]

    # On construit une liste de steps uniques (en évitant de tester des mappings identiques)
    unique_steps: List[int] = []
    seen_cost_maps = set()
    for step in range(max(5, MIN_STEP_CENTS), MAX_STEP_CENTS + 1):
        mapping = tuple((c + step - 1) // step for c in costs_cents)
        if mapping not in seen_cost_maps:
            seen_cost_maps.add(mapping)
            unique_steps.append(step)

    steps = unique_steps
    results_same: List[Tuple[int, Tuple]] = []
    best_result = None
    best_profit = -1.0
    best_cost = -1.0
    start_global = time.time()

    with mp.Pool(processes=min(len(steps), mp.cpu_count())) as pool:
        try:
            for result in pool.imap_unordered(
                _dp_for_step, [(actions, budget_eur, step) for step in steps]
            ):
                if time.time() - start_global >= time_limit:
                    pool.terminate()
                    pool.join()
                    break
                if result is None:
                    continue

                chosen, total_cost, total_profit, meta = result
                if best_result is None:
                    best_result = result
                    best_profit = total_profit
                    best_cost = total_cost
                    results_same.append((meta["step"], result))
                else:
                    if math.isclose(total_profit, best_profit, rel_tol=1e-9) and \
                       math.isclose(total_cost, best_cost, rel_tol=1e-9):
                        results_same.append((meta["step"], result))
                    elif total_profit > best_profit or (
                        math.isclose(total_profit, best_profit) and total_cost > best_cost
                    ):
                        best_result = result
                        best_profit = total_profit
                        best_cost = total_cost
                        results_same = [(meta["step"], result)]
        except Exception:
            pool.terminate()
            pool.join()
            raise

    if results_same:
        step_min, res_min = min(results_same, key=lambda x: x[0])
        chosen, total_cost, total_profit, meta = res_min
        meta["step"] = step_min
        return chosen, total_cost, total_profit, meta

    return [], 0.0, 0.0, {"algo": "dp", "step": MIN_STEP_CENTS}


# -----------------------------
# Sélecteur auto (uniquement DP)
# -----------------------------
def solve_auto(
    actions: List[Tuple[str, float, float]],
    budget: float
) -> Tuple[List[Tuple[str, float, float]], float, float, dict]:
    """
    Point d'entrée unique pour la résolution (actuellement DP uniquement).

    Args:
        actions: Liste (name, cost, rate).
        budget: Budget en euros.

    Returns:
        Tuple (chosen, total_cost, total_profit, meta).
    """
    return knapsack_dp_auto(actions, budget)


# -----------------------------
# Affichage
# -----------------------------
def display_solution(
    chosen: List[Tuple[str, float, float]],
    total_cost: float,
    total_profit: float,
    meta: dict
) -> None:
    """
    Affiche la solution trouvée (liste des noms, coût total et bénéfice total).

    Args:
        chosen: Liste d'actions retenues (name, cost, rate).
        total_cost: Coût total en euros.
        total_profit: Bénéfice total en euros.
        meta: Métadonnées de la méthode {"algo": "...", "step": ...}.
    """
    algo = meta.get("algo", "?")
    debug_print(f"\n[Solution] (méthode: {algo})")
    if algo == "dp" and "step" in meta:
        debug_print(f"Granularité DP : {meta['step']}")
    if not chosen:
        print("Aucune action sélectionnée.")
        return
    names = [n for (n, _, _) in chosen]
    print(", ".join(names))
    print(f"[Coût] {total_cost:.2f}€")
    print(f"[Bénéfice] {total_profit:.2f}€")


# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    global_start = time.time()
    rows, profit_format = load_csv_and_detect(FILE_PATH)
    actions = parse_actions(rows, profit_format)
    actions = pre_filter_actions(actions)
    chosen, total_cost, total_profit, meta = solve_auto(actions, BUDGET_MAX)
    display_solution(chosen, total_cost, total_profit, meta)
    print(f"\n[Chrono GLOBAL] {time.time() - global_start:.4f} s")
