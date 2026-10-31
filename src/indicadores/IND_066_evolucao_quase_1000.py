#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-066 — evolucao quase 1000; execução SOMENTE com --executar.

Este script é um invólucro: cálculos/validações em _ind055_072_core.py.
"""
from _ind055_072_core import main, Pendencia

if __name__ == '__main__':
    try:
        raise SystemExit(main(66))
    except (Pendencia, ValueError, FileExistsError) as exc:
        print('IND-066 BLOQUEADO:', exc, flush=True)
        raise SystemExit(2)
