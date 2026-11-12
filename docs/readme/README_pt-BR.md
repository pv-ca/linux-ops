<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../../docs/branding/linux-ops-surreal-textured-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="../../docs/branding/linux-ops-surreal-textured-light.png">
  <img src="../../docs/branding/linux-ops-surreal-textured-light.png" alt="linux-ops: um pinguim mecânico ajusta um terminal de pernas articuladas" width="340">
</picture>

### Desfaça o que seu agente de IA fez na sua máquina Linux.

[![Claude Code](https://img.shields.io/badge/Claude_Code-plugin-d97757?style=flat-square)](#instalação)
[![Codex](https://img.shields.io/badge/Codex-planejado-8a8a8a?style=flat-square)](#instalação)
[![Antigravity](https://img.shields.io/badge/Antigravity-planejado-8a8a8a?style=flat-square)](#instalação)
[![MIT](https://img.shields.io/badge/license-MIT-f4c430?style=flat-square)](../../LICENSE)
[![Status](https://img.shields.io/badge/status-inicial-8a8a8a?style=flat-square)](#instalação)

[English](../../README.md) · **Português (Brasil)**

[Exemplo](#a-mesma-pergunta-com-e-sem-ela) · [Quão bem funciona](#quão-bem-funciona) · [Instalação](#instalação) · [O que faz](#o-que-faz) · [Quando não usar](#quando-não-usar) · [Seus dados](#seus-dados) · [Sistemas suportados](#sistemas-suportados)

</div>

---

Seu agente instala um pacote, ativa um serviço e edita um arquivo em `/etc`. No dia seguinte algo quebrou, e uma sessão nova não faz ideia do que foi feito. O `/rewind` do Claude Code traz de volta os arquivos que o agente editou, mas não o que os comandos de shell dele mudaram.

A **linux-ops** guarda cada alteração que o agente faz junto com o comando que a reverte, e um hook grava todo comando que ele roda, caso ele esqueça de registrar algum. Assim uma sessão nova consegue responder duas perguntas:

- **O que mudou desde que funcionava?** O `/linux-ops:changes` compara retratos da máquina e o registro do próprio gerenciador de pacotes, então acha também mudanças que ninguém avisou.
- **Como eu volto atrás?** O `/linux-ops:undo` mostra cada alteração com o comando que a reverte, depois roda esse comando e confere o que ainda está diferente.

No Codex, no Antigravity e em outros agentes, peça a mesma coisa com palavras.

Os modelos já conhecem `apt` e `systemctl`. O que eles não têm é memória desta máquina: o que uma sessão anterior alterou, como reverter e como o sistema estava antes. É isso que a linux-ops guarda.

## A mesma pergunta, com e sem ela

Quatro coisas foram alteradas numa máquina Fedora sem avisar o agente: um pacote instalado, um arquivo de sysctl criado, um arquivo de configuração editado com a data atrasada em 30 dias, e outro arquivo de configuração apagado. Uma sessão nova recebeu o pedido de dizer o que mudou na última hora, uma alteração por linha.

<table>
<tr><th>Sem linux-ops</th><th>Com linux-ops</th></tr>
<tr><td>

```text
installed package: tree (tree-2.2.1-4.fc44.x86_64)
added config file: /etc/sysctl.d/99-tuning.conf
edited config file: /etc/myapp/app.conf
```

</td><td>

```text
installed package: tree (2.2.1-4.fc44)
added config file: /etc/sysctl.d/99-tuning.conf
edited config file: /etc/myapp/app.conf
deleted config file: /etc/myapp/legacy.conf
```

</td></tr>
</table>

Respostas reais de duas rodadas do [caso what-changed](../EVALS.md#what-changed), Claude Code com `claude-opus-5-5`. Um arquivo apagado que não pertence a nenhum pacote não deixa rastro para achar; só um retrato tirado antes ainda o lista.

## Quão bem funciona

Os mesmos pedidos, com e sem o plugin, num contêiner Fedora 44 novo, três rodadas cada. Claude Code com `claude-opus-5-5` em esforço alto, 11/11/2026. O [docs/EVALS.md](../EVALS.md) descreve os casos e o que conta como aprovação (em inglês).

| Caso | Com linux-ops | Sem |
| --- | --- | --- |
| **undo-yesterday**: uma sessão nova desfaz o que um agente fez no dia anterior e mantém o que a pessoa fez depois | 3 de 3 · 29 turnos · US$ 0,84 | 0 de 4 · 23 turnos · US$ 0,75 |
| **what-changed**: apontar quatro alterações não anunciadas, uma delas um arquivo apagado | 3 de 3 · 9 turnos · US$ 0,27 | 0 de 3 · 21 turnos · US$ 0,82 |

Turnos e custo são medianas por rodada. Três rodadas mostram um padrão, não uma taxa.

## Instalação

| Agente | O que você recebe | Situação |
| --- | --- | --- |
| Claude Code | skill, hooks, comandos e painel | suportado, medido |
| Codex | skill e hooks | planejado: instala, ainda não testado |
| Antigravity | skill e hooks | planejado: instala, ainda não testado |
| Qualquer outro agente | só a skill, sem hooks: o próprio agente grava o diário | não medido |

**Claude Code**

```bash
claude plugin marketplace add pv-ca/linux-ops && claude plugin install linux-ops@linux-ops
```

Isso instala para todos os projetos. Acrescente `--scope project` ao segundo comando para instalar só no projeto atual.

**Codex**

```bash
codex plugin marketplace add pv-ca/linux-ops && codex plugin add linux-ops@linux-ops
```

O Codex pede para você revisar os hooks na primeira vez.

**Antigravity**

```bash
agy plugin install https://github.com/pv-ca/linux-ops
```

Para um projeto só, clone o repositório em `.agents/plugins/linux-ops` dentro dele.

**Qualquer outro agente** (Cursor, OpenCode, Gemini CLI e os demais)

```bash
npx skills add pv-ca/linux-ops
```

Acrescente `-g` para instalar para todos os projetos.

Com o plugin instalado, todo comando de shell que o agente executa fica registrado na sua máquina, em todo projeto em que ele está ativo. [Seus dados](#seus-dados) diz o que fica guardado, onde, e como desligar ou remover.

**Confira se funciona.** Abra uma sessão nova e pergunte "o que mudou nesta máquina nas últimas duas semanas?", ou rode `/linux-ops:setup` no Claude Code. A resposta vem do registro do próprio gerenciador de pacotes, então funciona no primeiro dia, antes de existir qualquer retrato.

A mesma pasta serve aos três agentes: a skill e os scripts são compartilhados, e cada agente tem seu manifesto e seu arquivo de hooks, ambos pequenos.

## O que faz

| Peça | O que você recebe |
| --- | --- |
| Diário | Cada alteração é registrada com o que foi feito, o comando que a desfaz e o backup criado. Com o plugin, um hook também registra todo comando que o agente executa, e a sessão seguinte é avisada quando há comandos registrados sem nenhuma alteração declarada, então o registro não depende de o modelo lembrar. |
| Retratos | Pacotes do sistema, Flatpak e Snap, kernel e sua linha de comando, módulos carregados, estado do Secure Boot, unidades habilitadas (do sistema e do usuário), nomes de usuários e grupos, um hash de cada arquivo em `/etc` e em `~/.config`, e o dconf. Tirados no máximo uma vez por dia no início da sessão. Comparar dois deles responde "o que mudou?" a partir do que está no disco, incluindo mudanças que ninguém anunciou. |
| Plano de reversão | Um comando entrega ao agente as alterações ativas com seus comandos de reversão, o retrato anterior a elas e o que ainda está diferente dele, para que desfazer custe poucos passos. Os scripts nunca executam uma reversão sozinhos. |
| Histórico | O que o próprio gerenciador de pacotes registrou. Assim "o que mudou na semana passada?" tem resposta no dia em que você instala a linux-ops. |
| Perfil do sistema | Família da distribuição, gerenciador de pacotes, init, tipo de sessão, SELinux ou AppArmor, e se o sistema é um dos que a skill pode alterar. Aparece para o agente no início da sessão. |

Comandos, no Claude Code:

- `/linux-ops:undo`: reverte uma alteração registrada.
- `/linux-ops:changes`: o que mudou nesta máquina desde que funcionava.
- `/linux-ops:improve`: deixa a máquina melhor para o que você faz com ela. O agente pergunta o que você quer, mede, recomenda mudanças para este hardware e esta distribuição, aplica as que você escolher com o desfazer de cada uma e mede de novo.
- `/linux-ops:verify`: confere se tudo o que foi configurado aqui ainda funciona, por exemplo depois de uma atualização.
- `/linux-ops:preflight`: confere se a máquina está pronta para uma atualização ou um upgrade de versão.
- `/linux-ops:export`: o que foi configurado aqui, escrito para ser reproduzido em outra máquina.
- `/linux-ops:rescue`: uma folha de uma página para o dia em que a máquina não inicia e nenhum agente a alcança.
- `/linux-ops:setup`: primeiro retrato, o que mudou nas últimas duas semanas, e regras de permissão para que a inspeção somente leitura pare de pedir aprovação.
- `/linux-ops:data`: o que a linux-ops guarda e onde; apagar tudo, ou desligar o registro de comandos.

Nos outros agentes, peça a mesma coisa em palavras; a skill leva aos mesmos scripts.

No Claude Code um painel diz o que foi alterado nesta máquina, a alteração mais recente primeiro, cada uma com um botão **Undo** que só preenche o prompt para você enviar. Ele lê o diário direto e não gasta tokens do modelo. Escolha onde ele fica com `/linux-ops-panel chip|bar|side|off`; a escolha vale para as próximas sessões:

- `chip` (padrão): um rótulo discreto abaixo do prompt, "linux-ops · 2 changes"; ao clicar, abre um cartão de duas linhas acima do prompt com a máquina, a última alteração e o Undo dela.
- `bar`: uma linha acima do prompt com a última alteração e o Undo dela.
- `side`: um painel ao lado da conversa com a máquina (distribuição, kernel, ambiente gráfico, gerenciador de pacotes, init, SELinux ou AppArmor), as alterações por dia, a idade do último retrato e um botão para tirar outro.
- `off`: só uma linha de status enquanto houver alterações.

Os scripts ficam em `skills/linux-ops/scripts/` e requerem Python 3.6 ou superior, só com a biblioteca padrão. `detect_host.py` e `state.py` leem o sistema; `journal.py` e `state.py` gravam apenas em `~/.local/state/linux-ops/`.

## Quando não usar

A linux-ops compara estados e guarda comandos de reversão. Ela não restaura o sistema como um snapshot de sistema de arquivos faz, e nenhum dos dois tipos de retrato é um backup. O comando de reversão é escrito pelo agente e ninguém o confere: leia antes de deixar rodar.

- **Você quer voltar o sistema inteiro para ontem.** Use snapshots de sistema de arquivos, como o Snapper ou o Timeshift no Btrfs. A linux-ops funciona junto com eles: diz o que mudou e como desfazer só aquela mudança, sem perder todo o resto desde então.
- **Você administra muitas máquinas.** Use uma ferramenta de configuração como o Ansible, ou um sistema declarativo como o NixOS. A linux-ops é para a máquina em que o agente roda.
- **Você quer guardar cada versão de `/etc`.** O etckeeper põe `/etc` sob controle de versão, e os dois não atrapalham um ao outro.
- **Você não quer comandos registrados.** Defina `LINUX_OPS_NO_LOG=1`, ou instale só a skill, sem os hooks.

## Seus dados

| | |
| --- | --- |
| O que é registrado | Todo comando de shell que o agente executa, e cada arquivo que ele edita fora de um repositório Git, em todo projeto em que o plugin está ativo. A saída dos comandos não. |
| O que mais fica guardado | As alterações que o agente declara, e até 90 retratos (cerca de 1 MB cada, no máximo um por dia). |
| Onde | `~/.local/state/linux-ops/<machine-id>/` (com `-<contêiner>` no fim dentro de um distrobox ou outro contêiner), legível só por você. `journal.py where` mostra a pasta e o tamanho. |
| Por quanto tempo | O diário nunca é cortado. Retratos além dos 90 mais novos são apagados. |
| Quem vê | Os scripts não enviam nada para lugar nenhum. O que o agente lê do diário vai para o provedor do seu modelo, como qualquer outra saída de ferramenta. |
| Desligar o registro | `LINUX_OPS_NO_LOG=1` desliga o registro automático de comandos e mantém só as alterações que o agente declara. |
| Remover tudo | Desinstale o plugin com o comando do seu agente e apague `~/.local/state/linux-ops/`. |

Para relatar um problema de segurança, veja o [SECURITY.md](../../SECURITY.md) (em inglês).

Credenciais são mascaradas antes de o comando ser gravado: valores atribuídos ou passados a `password`, `token`, `secret`, `api key` ou `authorization`, senhas e tokens dentro de URLs, chaves privadas, e os argumentos de senha de ferramentas comuns (`curl -u`, `sshpass`, `mysql`, `nmcli`, `chpasswd`, `docker login`, `sudo -S` e mais algumas). Chaves do dconf cujo nome parece de credencial são guardadas como hash. A máscara é uma cortesia, não uma garantia: um segredo em um formato que ela não conhece fica guardado como foi digitado.

## Sistemas suportados

| Nível | Sistemas |
| --- | --- |
| Tier 1, testados na integração contínua | Fedora, Debian, Ubuntu, Arch Linux, openSUSE Tumbleweed, openSUSE Leap |
| Derivadas, não testadas | Distribuições que declaram uma dessas famílias em `ID_LIKE`, como Rocky, Linux Mint ou Manjaro |
| Demais sistemas | Alpine, Void, Gentoo, NixOS e qualquer outra distribuição. A detecção e os retratos são testados na integração contínua no Alpine; o resto não é testado. O perfil traz um aviso, e o agente confirma os nomes no próprio sistema. |

Foi feita para funcionar em qualquer distribuição, e nada nela recusa alguma. Onde os comandos comuns estariam errados, o perfil diz ao agente como aquele sistema é alterado: sistemas baseados em imagens (Fedora Silverblue, Kinoite, Bazzite, openSUSE MicroOS e Aeon) pela ferramenta de camadas deles, o NixOS pela configuração, máquinas sem systemd pelo init que usam, e contêineres sem gerenciador de serviços iniciando e parando o processo diretamente. O histórico de pacotes lê apenas rpm, dpkg e pacman. As regras estão em [docs/CONTRACT.md](../CONTRACT.md).

## Desenvolvimento

```console
$ python3 -m pytest -q tests     # testes unitários com sistemas de arquivos simulados
$ tests/containers.sh            # os scripts em cada imagem Tier 1 e no Alpine
```

`tests/containers.sh` requer Docker ou Podman e acesso à rede; use `ENGINE` para escolher entre eles.

## Licença

[MIT](../../LICENSE)
