---
name: papiro-windows
description: "Armadilhas do Windows tratadas pelo PAPIRO (PRD §3.2) e diferenças para o Linux."
---

# papiro-windows

## Restrições do Windows (PRD §3.2)
| Restrição | Tratamento obrigatório |
| --- | --- |
| Arquivo aberto em visualizador fica travado | Gravar em temporário e trocar com `os.replace`; detectar trava e avisar |
| Caminhos com acento e espaço | `PYTHONUTF8=1`, `pathlib` em tudo, testes com nomes como `Relatório — Márcio.pdf` |
| Limite de 260 caracteres no caminho | Ativar `LongPathsEnabled` e usar raiz curta `C:\PAPIRO` |
| Criar processos é caro | Workers persistentes: LibreOffice via unoserver, Chromium via Playwright, pool Python |
| Defender varre cada arquivo do lote | Exclusão opcional só da pasta temporária, com aviso de risco |
| Binários com nomes próprios do Windows | Resolvedor central de binários (ex.: `gswin64c.exe`, `soffice.com`) |
| Fontes do sistema em duas pastas | Indexar `C:\Windows\Fonts` e `%LOCALAPPDATA%\Microsoft\Windows\Fonts` |

## Perfis de hardware (PRD §3.3)
| Perfil | Como é detectado | IA local disponível | Uso típico |
| --- | --- | --- | --- |
| P0 — Só CPU | Nenhuma GPU utilizável | OCR Tesseract e PaddleOCR em CPU; Docling em CPU | Tudo, exceto modelos de visão pesados |
| P1 — GPU NVIDIA local | `nvidia-smi` responde | Modelos de visão para OCR em CUDA | Parsing de alta precisão na própria máquina |
| P2 — GPU AMD local | Adaptador AMD via DirectML ou Vulkan | ONNX via DirectML; GGUF via Ollama, LM Studio ou llama.cpp Vulkan | Modelos de visão de porte médio |
| P3 — Nó remoto Linux | Endpoint HTTP configurado | Modelos pesados na máquina Kubuntu com GPU AMD 16 GB (ROCm), em API compatível com OpenAI | Lotes grandes de documentos escaneados |

O perfil ativo fica em `papiro.toml` e o roteador (seção 9) só oferece motores compatíveis com ele.

## Como o código trata
- Raiz: pasta do repositório (C:\PAPIRO) ou `PAPIRO_HOME`; ativos (fontes, bin, modelos) sempre do repositório.
- Binários: `binfinder` procura em `bin\` (Windows) ou `bin/linux-x86_64` (Linux), depois PATH e Program Files.
- Hooks: `.claude/settings.json` (PowerShell) no Windows; `.claude/settings.linux.json` (Python) no Linux.

Fonte canônica: `docs/PAPIRO_PRD_ORIGINAL.md` (trechos acima copiados verbatim) e `docs/AGENTE_AUTONOMO_ENGENHARIA_PDF.md`. Ferramentas do MCP `papiro` respondem no envelope §8.1 (`ok`, `job_id`, `outputs`, `engine`, `qa`, `error`). Nunca declarar sucesso com `ok=false`.
