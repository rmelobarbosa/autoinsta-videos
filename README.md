# autoinsta-videos

Reels do **Auto Insta** (autoinsta.com.br) feitos pela Katy, a agente de vídeos.
Os vídeos ficam em `videos/` e o Metricool agenda a partir do link público
`https://raw.githubusercontent.com/rmelobarbosa/autoinsta-videos/main/videos/<arquivo>.mp4`.

## Como um vídeo é feito
Há dois tipos de cena, e dá para misturar no mesmo vídeo:

**Cena gráfica (padrão, não depende de navegador):** fundo de cor forte gerado pelo próprio motor
(`"bg": {"color": "#E4002B", "accent": "#FFC72C", "style": "rays"}` — estilos `plain`, `rays`, `dots`,
`stripes`, `grid`, `split`, `blob`) com texto gigante animado (`"type": "big"`, fontes Anton, Archivo Black
ou Poppins Black/ExtraBold, sombra dura opcional) e etiquetas inclinadas (`"type": "sticker"`).
Veja `exemplo/grafico.json` e o modelo do quadro `exemplo/quadro-curiosidade.json`.
Para dar ritmo: `"stagger": 0.25` no `big` faz cada linha entrar separada; `"type": "count"` faz um número subir animado
(só números que estão nas fontes); a barra de progresso no topo vem ligada (`"progress": false` desliga). Para ver só um fundo: `python3 engine/reel.py bg '{"color":"#1F3BFF","accent":"#FFFFFF","style":"rays"}' fundo.jpg`.

**Cena com foto:** a foto (1080x1920, sem texto) vem do Canva, capturada pelo navegador na nuvem
(`engine/reel.py stitch`) ou ajustada com `engine/reel.py prep`. Veja `exemplo/spec.json`.

Depois:
1. `python3 engine/reel.py check spec.json conferir.jpg` gera um quadro para conferir os textos.
2. `python3 engine/reel.py render spec.json videos/AAAA-MM-DD-tema.mp4` gera o vídeo (1080x1920, 30 fps, ~15–25 s, com trilha e efeitos).

Requisitos: Python 3 com Pillow e numpy, ffmpeg. Fontes Poppins, Anton e Archivo Black (licença OFL) em `assets/fonts/`.

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
