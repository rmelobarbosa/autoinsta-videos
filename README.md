# autoinsta-videos

Reels do **Auto Insta** (autoinsta.com.br) feitos pela Katy, a agente de vídeos.
Os vídeos ficam em `videos/` e o Metricool agenda a partir do link público
`https://raw.githubusercontent.com/rmelobarbosa/autoinsta-videos/main/videos/<arquivo>.mp4`.

## Como um vídeo é feito
1. As cenas (fotos com pessoas) são geradas no Canva no formato "Instagram Story" (1080x1920), **sem texto**.
2. Cada cena é capturada pelo navegador do app do Claude e ajustada com `python3 engine/reel.py prep <captura> <cena.jpg>`.
3. Um `spec.json` descreve as cenas, os textos animados e o card final (veja `exemplo/spec.json` e o topo de `engine/reel.py`).
4. `python3 engine/reel.py check spec.json conferir.jpg` gera um quadro para conferir os textos.
5. `python3 engine/reel.py render spec.json videos/AAAA-MM-DD-tema.mp4` gera o vídeo (1080x1920, 30 fps, ~15–25 s, sem música).

Requisitos: Python 3 com Pillow, ffmpeg. Fontes Poppins (licença OFL) em `assets/fonts/`.

## Som (automático)
Todo vídeo sai com **trilha sonora original** (gerada por código, sem direitos autorais) e **efeitos sonoros sincronizados** com as animações:
- card entrando → "pop"
- pílula de mensagem (`notif`) → som de notificação
- pílula verde (`ok`) → som de sucesso
- troca de cena → "vuush"
- logo no final → impacto com brilho

Volume final no padrão do Reels (-14 LUFS). Opções no `spec.json`:
```json
"audio": {"seed": 7, "music": true, "sfx": true, "music_volume": 1.0}
```
`seed` muda a música (andamento, tom, acordes e melodia). Cada item aceita `"sfx": "none"` para ficar sem som.
