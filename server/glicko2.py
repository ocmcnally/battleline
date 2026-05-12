"""Glicko-2 rating system — single-game update."""
import math

_SCALE = 173.7178
_TAU   = 0.5   # system constant controlling volatility change rate


def _g(phi: float) -> float:
    return 1.0 / math.sqrt(1 + 3 * phi**2 / math.pi**2)


def _E(mu: float, mu_j: float, phi_j: float) -> float:
    return 1.0 / (1 + math.exp(-_g(phi_j) * (mu - mu_j)))


def _new_volatility(phi: float, sigma: float, delta: float, v: float) -> float:
    """Illinois algorithm to converge on new volatility."""
    a      = math.log(sigma**2)
    delta2 = delta**2
    phi2   = phi**2

    def f(x: float) -> float:
        ex = math.exp(x)
        return (ex * (delta2 - phi2 - v - ex) / (2 * (phi2 + v + ex)**2)
                - (x - a) / _TAU**2)

    A = a
    if delta2 > phi2 + v:
        B = math.log(delta2 - phi2 - v)
    else:
        k = 1
        while f(a - k * _TAU) < 0:
            k += 1
        B = a - k * _TAU

    fA, fB = f(A), f(B)
    for _ in range(100):
        C  = A + (A - B) * fA / (fB - fA)
        fC = f(C)
        if fC * fB <= 0:
            A, fA = B, fB
        else:
            fA /= 2
        B, fB = C, fC
        if abs(B - A) < 1e-6:
            break
    return math.exp(A / 2)


def update(
    r: float, rd: float, sigma: float,
    r_opp: float, rd_opp: float,
    score: float,
) -> tuple[float, float, float]:
    """
    Return (new_r, new_rd, new_sigma) after one game.
    score: 1.0 = win, 0.5 = draw, 0.0 = loss
    """
    mu    = (r     - 1500) / _SCALE
    phi   = rd     / _SCALE
    mu_j  = (r_opp - 1500) / _SCALE
    phi_j = rd_opp / _SCALE

    g_j   = _g(phi_j)
    e_j   = _E(mu, mu_j, phi_j)
    v     = 1.0 / (g_j**2 * e_j * (1 - e_j))
    delta = v * g_j * (score - e_j)

    new_sigma = _new_volatility(phi, sigma, delta, v)
    phi_star  = math.sqrt(phi**2 + new_sigma**2)
    new_phi   = 1.0 / math.sqrt(1.0 / phi_star**2 + 1.0 / v)
    new_mu    = mu + new_phi**2 * g_j * (score - e_j)

    return (
        _SCALE * new_mu + 1500,
        _SCALE * new_phi,
        new_sigma,
    )
