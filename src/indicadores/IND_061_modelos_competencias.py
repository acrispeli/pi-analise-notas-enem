#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-061 — modelos competencias; execução SOMENTE com --executar.

Este script é um invólucro: cálculos/validações em _ind055_072_core.py.
"""
from _ind055_072_core import main, Pendencia

if __name__ == '__main__':
    try:
        raise SystemExit(main(61))
    except (Pendencia, ValueError, FileExistsError) as exc:
        print('IND-061 BLOQUEADO:', exc, flush=True)
        raise SystemExit(2)
