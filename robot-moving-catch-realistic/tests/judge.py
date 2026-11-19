"""End-state rules of the catch cell (docs/MANUAL.md, section 7), applied to the robot's own record."""
import cell

REQUIRED = 1           # parts that must be delivered


def inside(pos, basket, top):
    bx, by = basket
    return abs(pos[0] - bx) <= cell.BASKET_INNER[0] / 2 and abs(pos[1] - by) <= cell.BASKET_INNER[1] / 2 and pos[2] <= top


def judge(facts, now, sense, finished, within_budget=True):
    basket = facts["basket"]
    status = now["status"]
    delivered = [k for k, s in enumerate(status) if s == "delivered" and inside(now[f"part{k}"]["pos"], basket, cell.BASKET_HEIGHT + cell.ROLLER_RADIUS)]
    blocks = [inside(now[f"block{i}"]["pos"], basket, cell.BASKET_HEIGHT + 0.05) for i in range(3)]
    parked = all(abs(q - p) <= cell.PARK_TOLERANCE for q, p in zip(sense["joints"], cell.PARK)) and sense["finger_gap"] >= cell.PARK_GAP - 1e-4
    verdict = {"delivered_enough": len(delivered) >= REQUIRED, "basket_blocks_in_place": all(blocks), "parked": bool(parked),
               "finished": bool(finished), "within_budget": bool(within_budget)}
    verdict["overall"] = int(all(verdict.values()))
    verdict["notes"] = f"tries {status}, parts delivered and still in the basket {delivered}, basket blocks inside {blocks}"
    return verdict


BEFORE, AFTER = 10, 30        # arm actions allowed before the try is started, and after it is over


def within_budget(actions):
    """True when a recorded list of actions keeps both limits."""
    kinds = [a["kind"] for a in actions]
    cut = kinds.index("pass") if "pass" in kinds else len(kinds)
    return cut <= BEFORE and len(kinds) - cut - ("pass" in kinds) <= AFTER


def judge_world(world, finished, within=True):
    return judge(world.facts, world.truth(), world.sense(), finished, within)
