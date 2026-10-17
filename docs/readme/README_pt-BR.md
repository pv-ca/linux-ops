<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../../docs/branding/linux-ops-surreal-textured-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="../../docs/branding/linux-ops-surreal-textured-light.png">
  <img src="../../docs/branding/linux-ops-surreal-textured-light.png" alt="linux-ops: um pinguim mecânico ajusta um terminal de pernas articuladas" width="340">
</picture>

### Seu agente para administrar o Linux.

[![Claude Code](https://img.shields.io/badge/Claude_Code-skill-d97757?style=flat-square)](#instalação)
[![Codex](https://img.shields.io/badge/Codex-skill-10a37f?style=flat-square)](#instalação)
[![MIT](https://img.shields.io/badge/license-MIT-f4c430?style=flat-square)](../../LICENSE)
[![Status](https://img.shields.io/badge/status-rascunho-8a8a8a?style=flat-square)](#instalação)

[English](../../README.md) · **Português (Brasil)**

[Instalação](#instalação) · [O que faz](#o-que-faz) · [Sistemas suportados](#sistemas-suportados) · [Desenvolvimento](#desenvolvimento)

</div>

---

**linux-ops** ajuda seu agente a administrar a máquina Linux em que ele está sendo executado. Fornece um perfil do sistema, um método para alterações reversíveis e limites claros em sistemas não suportados.

> Rascunho inicial, versão 0.1.0.

Os modelos já conhecem `apt` e `systemctl`. O que falta é o estado desta máquina e a disciplina para alterá-la de forma reversível. É isso que a skill fornece.

## Instalação

Copie `skills/linux-ops` para a pasta de skills do seu agente, por exemplo `~/.claude/skills/linux-ops` para Claude Code ou `~/.agents/skills/linux-ops` para Codex.

## O que faz

- `skills/linux-ops/SKILL.md`: o método, com evidências, alterações em etapas reversíveis e os limites que exigem confirmação.
- `skills/linux-ops/scripts/detect_host.py`: exibe o perfil do sistema em JSON. Apenas lê a máquina, sem alterá-la. Requer Python 3.6 ou superior e usa somente a biblioteca padrão.

```console
$ python3 skills/linux-ops/scripts/detect_host.py --compact
{"change_model": "imperative", "environment": "physical", "family": "fedora", "init": "systemd", "mode": "read-write", "package_manager": "dnf", ...}
```

## Sistemas suportados

| Nível | Sistemas |
| --- | --- |
| Tier 1, testados na integração contínua | Fedora, Debian, Ubuntu, Arch Linux, openSUSE Tumbleweed, openSUSE Leap |
| Derivadas, não testadas | Distribuições que declaram uma dessas famílias em `ID_LIKE`, como Rocky, Linux Mint ou Manjaro |
| Demais sistemas | Modo somente leitura: a skill inspeciona e orienta, sem fazer alterações |

Sistemas baseados em imagens (Fedora Silverblue e Kinoite, openSUSE MicroOS e Aeon), NixOS e máquinas sem systemd permanecem no modo somente leitura. As regras estão em [docs/CONTRACT.md](../CONTRACT.md).

## Desenvolvimento

```console
$ python3 -m pytest -q tests     # testes unitários com sistemas de arquivos simulados
$ tests/containers.sh            # detector em cada imagem de contêiner Tier 1
```

`tests/containers.sh` requer Docker ou Podman e acesso à rede; use `ENGINE` para escolher entre eles.

## Licença

[MIT](../../LICENSE)
