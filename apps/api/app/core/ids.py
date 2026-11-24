import secrets
import threading
import time
import uuid

_RAND_BITS = 74  # rand_a (12) + rand_b (62)
_RAND_MAX = (1 << _RAND_BITS) - 1
# Começa abaixo da metade do espaço: sobra folga para incrementar dentro do mesmo milissegundo.
_START_MASK = (1 << (_RAND_BITS - 1)) - 1
_MAX_STEP = 1 << 32

_lock = threading.Lock()
_last_ms = 0
_last_rand = 0


def uuid7() -> uuid.UUID:
    """UUID versão 7 (RFC 9562) monótono neste processo.

    48 bits de timestamp em ms + 74 bits aleatórios. Dentro do mesmo milissegundo, a parte
    aleatória é incrementada por um passo aleatório (RFC 9562, §6.2, método 2), então ids
    gerados em sequência saem sempre em ordem: paginação e ordenação por id ficam corretas.
    """
    global _last_ms, _last_rand
    with _lock:
        now_ms = time.time_ns() // 1_000_000
        if now_ms > _last_ms:
            rand = secrets.randbits(_RAND_BITS) & _START_MASK
        else:
            now_ms = _last_ms  # relógio igual (ou voltou): mantém o tempo e incrementa
            rand = _last_rand + 1 + secrets.randbelow(_MAX_STEP)
            if rand > _RAND_MAX:  # praticamente impossível; avança 1 ms para não estourar
                now_ms += 1
                rand = secrets.randbits(_RAND_BITS) & _START_MASK
        _last_ms, _last_rand = now_ms, rand

    rand_a = rand >> 62
    rand_b = rand & ((1 << 62) - 1)
    value = (now_ms << 80) | (0x7 << 76) | (rand_a << 64) | (0b10 << 62) | rand_b
    return uuid.UUID(int=value)
