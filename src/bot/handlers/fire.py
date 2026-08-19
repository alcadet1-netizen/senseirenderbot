import logging
import random
import re
import secrets
import asyncio
import html
from typing import List, Optional, Tuple

from aiogram import F, Router
from aiogram.types import Message
from aiogram.enums import ChatMemberStatus

from src.core.config import settings
from src.core.container import Container
from src.core.visuals import Visuals

router = Router(name="fire_command")
logger = logging.getLogger(__name__)

FIRE_EMOJI_POOL = [
    "🔥", "💥", "⚡", "✨", "💫", "🌟", "⭐", "🌠", "☄️", "💢", "💯", "🎆", "🎇",
    "😀", "😃", "😄", "😁", "😆", "😅", "🤣", "😂", "🙂", "😊", "😇", "🥰", "😍",
    "🤩", "😘", "😗", "😚", "😋", "😛", "😜", "🤪", "😝", "🤑", "🤗", "🤭", "🤫",
    "🤔", "🤐", "🤨", "😐", "😑", "😶", "😏", "😒", "🙄", "😬", "🤥", "😌", "😔",
    "😪", "🤤", "😴", "😷", "🤒", "🤕", "🤢", "🤮", "🤧", "🥵", "🥶", "🥴", "😵",
    "🤯", "🤠", "🥳", "🥸", "😎", "🤓", "🧐", "😕", "😟", "🙁", "😮", "😯", "😲",
    "😳", "🥺", "😦", "😧", "😨", "😰", "😥", "😢", "😭", "😱", "😖", "😣", "😞",
    "😓", "😩", "😫", "🥱", "😤", "😡", "😠", "🤬", "😈", "👿", "💀", "☠️", "💩",
    "🤡", "👹", "👺", "👻", "👽", "👾", "🤖", "🎃", "😺", "😸", "😹", "😻", "😼",
    "😽", "🙀", "😿", "😾",
    "👋", "🤚", "🖐️", "✋", "🖖", "👌", "🤌", "🤏", "✌️", "🤞", "🤟", "🤘", "🤙",
    "👈", "👉", "👆", "🖕", "👇", "☝️", "👍", "👎", "✊", "👊", "🤛", "🤜", "👏",
    "🙌", "👐", "🤲", "🤝", "🙏", "✍️", "💅", "🤳", "💪", "🦾", "🦿",
    "👶", "🧒", "👦", "👧", "🧑", "👱", "👨", "🧔", "👩", "🧓", "👴", "👵", "🙍",
    "🙎", "🙅", "🙆", "💁", "🙋", "🧏", "🙇", "🤦", "🤷", "👮", "🕵️", "💂", "🥷",
    "👷", "🤴", "👸", "👳", "👲", "🧕", "🤵", "👰", "🤰", "🤱", "👼", "🎅", "🤶",
    "🦸", "🦹", "🧙", "🧚", "🧛", "🧜", "🧝", "🧞", "🧟", "💆", "💇", "🚶", "🧍",
    "🧎", "🏃", "💃", "🕺", "🕴️", "👯", "🧖", "🧗", "🤸", "🏌️", "🏇", "⛷️", "🏂",
    "👁️", "👀", "👂", "🦻", "👃", "🧠", "🫀", "🫁", "🦷", "🦴", "👅", "👄", "💋",
    "❤️", "🧡", "💛", "💚", "💙", "💜", "🖤", "🤍", "🤎", "💔", "❣️", "💕", "💞",
    "💓", "💗", "💖", "💘", "💝", "💟", "❤️‍🔥", "❤️‍🩹", "🫶",
    "🐶", "🐱", "🐭", "🐹", "🐰", "🦊", "🐻", "🐼", "🐻‍❄️", "🐨", "🐯", "🦁", "🐮",
    "🐷", "🐸", "🐵", "🙈", "🙉", "🙊", "🐒", "🐔", "🐧", "🐦", "🐤", "🐣", "🐥",
    "🦆", "🦅", "🦉", "🦇", "🐺", "🐗", "🐴", "🦄", "🐝", "🪱", "🐛", "🦋", "🐌",
    "🐞", "🐜", "🪰", "🪲", "🪳", "🦟", "🦗", "🕷️", "🦂", "🐢", "🐍", "🦎", "🦖",
    "🦕", "🐙", "🦑", "🦐", "🦞", "🦀", "🐡", "🐠", "🐟", "🐬", "🐳", "🐋", "🦈",
    "🐊", "🐅", "🐆", "🦓", "🦍", "🦧", "🐘", "🦛", "🦏", "🐪", "🐫", "🦒",
    "🦘", "🦬", "🐃", "🐂", "🐄", "🐎", "🐖", "🐏", "🐑", "🦙", "🐐", "🦌", "🐕",
    "🐩", "🦮", "🐕‍🦺", "🐈", "🐈‍⬛", "🪶", "🐓", "🦃", "🦤", "🦚", "🦜", "🦢", "🦩",
    "🕊️", "🐇", "🦝", "🦨", "🦡", "🦫", "🦦", "🦥", "🐁", "🐀", "🐿️", "🦔",
    "🌵", "🎄", "🌲", "🌳", "🌴", "🪵", "🌱", "🌿", "☘️", "🍀", "🎍", "🪴", "🎋",
    "🍃", "🍂", "🍁", "🍄", "🐚", "🪨", "🌾", "💐", "🌷", "🌹", "🥀", "🌺", "🌸",
    "🌼", "🌻", "🌞", "🌝", "🌛", "🌜", "🌚", "🌕", "🌖", "🌗", "🌘", "🌑", "🌒",
    "🌓", "🌔", "🌙", "🌎", "🌍", "🌏", "🪐", "💫", "⭐", "🌟", "✨", "⚡", "☄️",
    "💥", "🔥", "🌪️", "🌈", "☀️", "🌤️", "⛅", "🌥️", "☁️", "🌦️", "🌧️", "⛈️", "🌩️",
    "🌨️", "❄️", "☃️", "⛄", "🌬️", "💨", "💧", "💦", "☔", "☂️", "🌊", "🌫️",
    "🍏", "🍎", "🍐", "🍊", "🍋", "🍌", "🍉", "🍇", "🍓", "🫐", "🍈", "🍒", "🍑",
    "🥭", "🍍", "🥥", "🥝", "🍅", "🍆", "🥑", "🥦", "🥬", "🥒", "🌶️", "🫑", "🌽",
    "🥕", "🫒", "🧄", "🧅", "🥔", "🍠", "🥐", "🥯", "🍞", "🥖", "🥨", "🧀", "🥚",
    "🍳", "🧈", "🥞", "🧇", "🥓", "🥩", "🍗", "🍖", "🦴", "🌭", "🍔", "🍟", "🍕",
    "🫓", "🥪", "🥙", "🧆", "🌮", "🌯", "🫔", "🥗", "🥘", "🫕", "🥫", "🍝", "🍜",
    "🍲", "🍛", "🍣", "🍱", "🥟", "🦪", "🍤", "🍙", "🍚", "🍘", "🍥", "🥠", "🥮",
    "🍢", "🍡", "🍧", "🍨", "🍦", "🥧", "🧁", "🍰", "🎂", "🍮", "🍭", "🍬", "🍫",
    "🍿", "🍩", "🍪", "🌰", "🥜", "🍯", "🥛", "🍼", "🫖", "☕", "🍵", "🧃", "🥤",
    "🧋", "🍶", "🍺", "🍻", "🥂", "🍷", "🥃", "🍸", "🍹", "🧉", "🍾", "🧊", "🥄",
    "🍴", "🍽️", "🥣", "🥡", "🥢", "🧂",
    "⚽", "🏀", "🏈", "⚾", "🥎", "🎾", "🏐", "🏉", "🥏", "🎱", "🪀", "🏓", "🏸",
    "🏒", "🏑", "🥍", "🏏", "🪃", "🥅", "⛳", "🪁", "🏹", "🎣", "🤿", "🥊", "🥋",
    "🎽", "🛹", "🛼", "🛷", "⛸️", "🥌", "🎿", "⛷️", "🏂", "🪂", "🏋️", "🤼", "🤸",
    "🤺", "⛹️", "🤾", "🏌️", "🏇", "🧘", "🏄", "🏊", "🤽", "🚣", "🧗", "🚵", "🚴",
    "🏆", "🥇", "🥈", "🥉", "🏅", "🎖️", "🏵️", "🎗️", "🎫", "🎟️", "🎪",
    "🎮", "🕹️", "🎰", "🎲", "🧩", "🧸", "🪆", "♠️", "♥️", "♦️", "♣️", "♟️", "🃏",
    "🀄", "🎴", "🎭", "🖼️", "🎨", "🧵", "🪡", "🧶", "🪢",
    "🎼", "🎵", "🎶", "🎙️", "🎚️", "🎛️", "🎤", "🎧", "📻", "🎷", "🪗", "🎸", "🎹",
    "🎺", "🎻", "🪕", "🥁", "🪘",
    "⌚", "📱", "📲", "💻", "⌨️", "🖥️", "🖨️", "🖱️", "🖲️", "🗜️", "💽", "💾",
    "💿", "📀", "📼", "📷", "📸", "📹", "🎥", "📽️", "🎞️", "📞", "☎️", "📟", "📠",
    "📺", "📻", "🎙️", "🎚️", "🎛️", "🧭", "⏱️", "⏲️", "⏰", "🕰️", "⌛", "⏳", "📡",
    "🔋", "🔌", "💡", "🔦", "🕯️", "🪔", "🧯", "🛢️", "💸", "💵", "💴", "💶", "💷",
    "🪙", "💰", "💳", "💎", "⚖️", "🪜", "🧰", "🪛", "🔧", "🔨", "⚒️", "🛠️", "⛏️",
    "🪚", "🔩", "⚙️", "🪤", "🧱", "⛓️", "🧲", "🔫", "💣", "🧨", "🪓", "🔪", "🗡️",
    "⚔️", "🛡️", "🚬", "⚰️", "🪦", "⚱️", "🏺", "🔮", "📿", "🧿", "💈", "⚗️", "🔭",
    "🔬", "🕳️", "🩹", "🩺", "💊", "💉", "🩸", "🧬", "🦠", "🧫", "🧪",
    "🚗", "🚕", "🚙", "🚌", "🚎", "🚎", "🚓", "🚑", "🚒", "🚐", "🚚", "🚛",
    "🚜", "🦯", "🦽", "🦼", "🚴", "🚵", "🚶", "🛵", "🏍️", "🚨", "🚔", "🚍", "🚘",
    "🚖", "🚡", "🚠", "🚟", "🚃", "🚋", "🚞", "🚝", "🚄", "🚅", "🚈", "🚂", "🚆",
    "🚇", "🚊", "🚉", "✈️", "🛫", "🛬", "🛩️", "💺", "🛰️", "🚀", "🛸", "🚁", "🛶",
    "⛵", "🚤", "🛥️", "🛳️", "⛴️", "🚢", "⚓", "🪝", "⛽", "🚧", "🚦", "🚥", "🚏",
    "🗺️", "🗿", "🗽", "🗼", "🏰", "🏯", "🏟️", "🎡", "🎢", "🎠", "⛲", "⛱️", "🏖️",
    "🏝️", "🏜️", "🌋", "⛰️", "🏔️", "🗻", "🏕️", "⛺", "🏠", "🏡", "🏘️", "🏚️",
    "🏗️", "🏭", "🏢", "🏬", "🏣", "🏤", "🏥", "🏦", "🏨", "🏪", "🏫", "🏩", "💒",
    "🏛️", "⛪", "🕌", "🕍", "🛕", "🕋", "⛩️", "🛤️", "🛣️", "🗾", "🎑", "🏞️", "🌅",
    "🌄", "🌠", "🎇", "🎆", "🌇", "🌆", "🏙️", "🌃", "🌌", "🌉", "🌁",
    "👓", "🕶️", "🥽", "🥼", "🦺", "👔", "👕", "👖", "🧣", "🧤", "🧥", "🧦", "👗",
    "👘", "🥻", "🩱", "🩲", "🩳", "👙", "👚", "👛", "👜", "👝", "🛍️", "🎒", "🩴",
    "👞", "👟", "🥾", "🥿", "👠", "👡", "🩰", "👢", "👑", "👒", "🎩", "🎓", "🧢",
    "🪖", "⛑️", "📿", "💄", "💍", "💎", "🔇", "🔈", "🔉", "🔊", "📢", "📣", "📯",
    "🔔", "🔕", "🎵", "🎶", "🎼", "🎤", "🎧", "📻", "🎷", "🪗", "🎸", "🎹", "🎺",
    "🎻", "🪕", "🥁", "🪘", "📱", "📲", "☎️", "📞", "📟", "📠", "🔋", "🔌", "💻",
    "🖥️", "🖨️", "⌨️", "🖱️", "🖲️", "💽", "💾", "💿", "📀", "🧮", "🎥", "🎞️", "📽️",
    "🎬", "📺", "📷", "📸", "📹", "📼", "🔍", "🔎", "🕯️", "💡", "🔦", "🏮", "🪔",
    "📔", "📕", "📖", "📗", "📘", "📙", "📚", "📓", "📒", "📃", "📜", "📄", "📰",
    "🗞️", "📑", "🔖", "🏷️", "💰", "🪙", "💴", "💵", "💶", "💷", "💸", "💳", "🧾",
    "💹", "✉️", "📧", "📨", "📩", "📤", "📥", "📦", "📫", "📪", "📬", "📭", "📮",
    "🗳️", "✏️", "✒️", "🖋️", "🖊️", "🖌️", "🖍️", "📝", "💼", "📁", "📂", "🗂️", "📅",
    "📆", "🗒️", "🗓️", "📇", "📈", "📉", "📊", "📋", "📌", "📍", "📎", "🖇️", "📏",
    "📐", "✂️", "🗃️", "🗄️", "🗑️", "🔒", "🔓", "🔏", "🔐", "🔑", "🗝️", "🔨", "🪓",
    "⛏️", "⚒️", "🛠️", "🗡️", "⚔️", "🔫", "🪃", "🏹", "🛡️", "🪚", "🔧", "🪛", "🔩",
    "⚙️", "🗜️", "⚖️", "🦯", "🔗", "⛓️", "🪝", "🧰", "🧲", "🪜", "⚗️", "🧪", "🧫",
    "🧬", "🔬", "🔭", "📡", "💉", "🩸", "💊", "🩹", "🩺", "🚪", "🛗", "🪞", "🪟",
    "🛏️", "🛋️", "🪑", "🚽", "🪠", "🚿", "🛁", "🪤", "🪒", "🧴", "🧷", "🧹", "🧺",
    "🧻", "🪣", "🧼", "🪥", "🧽", "🧯", "🛒", "🚬", "⚰️", "🪦", "⚱️", "🗿", "🪧",
    "🏧", "🚮", "🚳", "♿", "🚹", "🚺", "🚻", "🚾", "🛂", "🛃", "🛄", "🛅",
    "⚠️", "🚸", "⛔", "🚫", "🚳", "🚭", "🚯", "🚱", "📵", "🔞", "☢️", "☣️",
    "⬆️", "↗️", "➡️", "↘️", "⬇️", "↙️", "⬅️", "↖️", "↕️", "↔️", "↩️", "↪️", "⤴️",
    "⤵️", "🔃", "🔄", "🔙", "🔚", "🔛", "🔜", "🔝", "🛐", "⚛️", "🕉️", "✡️", "☸️",
    "☯️", "✝️", "☦️", "☪️", "☮️", "🕎", "🔯", "♈", "♉", "♊", "♋", "♌", "♍",
    "♎", "♏", "♐", "♑", "♒", "♓", "⛎", "🔀", "🔁", "🔂", "▶️", "⏩", "⏭️",
    "⏯️", "◀️", "⏪", "⏮️", "🔼", "⏫", "🔽", "⏬", "⏸️", "⏹️", "⏺️", "⏏️", "🎦",
    "🔅", "🔆", "📶", "📳", "📴", "♀️", "♂️", "⚧️", "✖️", "➕", "➖", "➗", "♾️",
    "‼️", "⁉️", "❓", "❔", "❕", "❗", "〰️", "💱", "💲", "⚕️", "♻️", "⚜️", "🔱",
    "📛", "🔰", "⭕", "✅", "☑️", "✔️", Visuals.cross_raw(), "❎", "➰", "➿", "〽️", "✳️", "✴️",
    "❇️", "©️", "®️", "™️", "#️⃣", "*️⃣", "0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣",
    "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟", "🔠", "🔡", "🔢", "🔣", "🔤", "🅰️", "🆎", "🅱️",
    "🆑", "🆒", "🆓", "ℹ️", "🆔", "Ⓜ️", "🆕", "🆖", "🅾️", "🆗", "🅿️", "🆘", "🆙",
    "🆚", "🈁", "🈂️", "🈷️", "🈶", "🈯", "🉐", "🈹", "🈚", "🈲", "🈱", "🈸", "🈴",
    "🈳", "㊗️", "㊙️", "🈺", "🈵", "🔴", "🟠", "🟡", "🟢", "🔵", "🟣", "🟤", "⚫",
    "⚪", "🟥", "🟧", "🟨", "🟩", "🟦", "🟪", "🟫", "⬛", "⬜", "◼️", "◻️", "◾",
    "◽", "▪️", "▫️", "🔶", "🔷", "🔸", "🔹", "🔺", "🔻", "💠", "🔘", "🔳", "🔲",
    "🏁", "🚩", "🎌", "🏴", "🏳️", "🏳️‍🌈", "🏳️‍⚧️", "🏴‍☠️", "🇦🇨", "🇦🇩", "🇦🇪",
    "🇦🇫", "🇦🇬", "🇦🇮", "🇦🇱", "🇦🇲", "🇦🇴", "🇦🇶", "🇦🇷", "🇦🇸", "🇦🇹", "🇦🇺",
    "🇦🇼", "🇦🇽", "🇦🇿", "🇧🇦", "🇧🇧", "🇧🇩", "🇧🇪", "🇧🇫", "🇧🇬", "🇧🇭", "🇧🇮",
    "🇧🇯", "🇧🇱", "🇧🇲", "🇧🇳", "🇧🇶", "🇧🇷", "🇧🇸", "🇧🇹", "🇧🇻", "🇧🇼",
    "🇧🇾", "🇧🇿", "🇨🇦", "🇨🇨", "🇨🇩", "🇨🇫", "🇨🇬", "🇨🇭", "🇨🇮", "🇨🇰", "🇨🇱",
    "🇨🇲", "🇨🇳", "🇨🇴", "🇨🇵", "🇨🇷", "🇨🇺", "🇨🇻", "🇨🇼", "🇨🇽", "🇨🇾", "🇨🇿",
    "🇩🇪", "🇩🇬", "🇩🇯", "🇩🇰", "🇩🇲", "🇩🇴", "🇩🇿", "🇪🇦", "🇪🇨", "🇪🇪", "🇪🇬",
    "🇪🇭", "🇪🇷", "🇪🇸", "🇪🇹", "🇪🇺", "🇫🇮", "🇫🇯", "🇫🇰", "🇫🇲", "🇫🇴", "🇫🇷",
    "🇬🇦", "🇬🇧", "🇬🇩", "🇬🇪", "🇬🇫", "🇬🇬", "🇬🇬", "🇬🇭", "🇬🇮", "🇬🇱", "🇬🇲", "🇬🇳",
    "🇬🇵", "🇬🇶", "🇬🇷", "🇬🇸", "🇬🇹", "🇬🇺", "🇬🇼", "🇬🇾", "🇭🇰", "🇭🇲", "🇭🇳",
    "🇭🇷", "🇭🇹", "🇭🇺", "🇮🇨", "🇮🇩", "🇮🇪", "🇮🇱", "🇮🇲", "🇮🇳", "🇮🇴", "🇮🇶",
    "🇮🇷", "🇮🇸", "🇮🇹", "🇯🇪", "🇯🇲", "🇯🇾", "🇯🇪", "🇯🇲", "🇯🇺", "🇯🇺", "🇯🇵", "🇟🇰", "🇰𝜔",
    "🇰𝜔", "🇱𝜀", "🇱𝜀", "🇱𝜆", "🇱𝜆", "🇲𝜀", "🇲𝜆", "🇲𝜈", "🇲𝜒", "🇲𝜓", "🇳𝜀",
    "🇴𝜆", "🇵𝜆", "🇨𝜀", "🇶𝜀", "🇷𝜇", "🇸𝜀", "🇹𝜇", "🇺𝜎", "🇺𝜈", "🇶𝜀", "🇿𝜂",
    "🇿𝜃", "🇩󠁧󠁢󠁥󠁮󠁧󠁿", "🇩󠁧󠁢󠁳󠁣󠁴󠁿", "🇩󠁧󠁢󠁷󠁬󠁳󠁿"
]

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{5,32}$")


def _build_fire_href(user_id: int, username: Optional[str]) -> str:
    username = (username or "").lstrip("@").strip()
    if username and USERNAME_RE.fullmatch(username):
        return f"tg://resolve?domain={username}"
    return f"tg://user?id={user_id}"


def _fmt_name(username: Optional[str], user_id: int) -> str:
    username = (username or "").lstrip("@").strip()
    return f"@{username}" if username and USERNAME_RE.fullmatch(username) else f"#{str(user_id)[-4:]}"


def _frame(lines: List[str], width: int = 32) -> str:
    """Создает рамку вокруг текста (Left-only style)."""
    result = [Visuals.frame_top_left(width)]
    for line in lines:
        # Пытаемся определить выравнивание или просто лепим влево
        # Visuals.frame_line обрезает длинные строки
        result.append(Visuals.frame_line_left(line, width))
    result.append(Visuals.frame_bottom_left(width))
    return "<pre>\n" + "\n".join(result) + "\n</pre>"


def build_fire_drop_html(sender: str, is_admin: bool, source: str,
                         tags: List[Tuple[int, Optional[str], int]]) -> str:
    total = sum(c for _, _, c in tags)
    total_usdt = total * 0.0002
    tx = f"{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}"

    fire_header = Visuals.fire()

    lines = [
        f"{fire_header} SENSEI FIRE DROP",
        f"От: {sender}",
        f"Источник: {source}",
        f"💰 {total:,} (~{total_usdt:.2f} USDT)",
        f"👥 Получателей: {len(tags)}",
        f"TX: {tx}",
        "🎁 Получили:",
    ]

    # Добавляем список получателей в рамку (по 2 в строку)
    for i in range(0, len(tags), 2):
        chunk = tags[i:i+2]
        # Формируем строку вида "@user1 +100 | @user2 +100"
        line_content = " | ".join(f"{_fmt_name(u, uid)} +{c}" for uid, u, c in chunk)
        lines.append(line_content)

    terminal = _frame(lines, width=32)

    emoji_parts = [f'<a href="{_build_fire_href(uid, u)}">{FIRE_EMOJI_POOL[i % len(FIRE_EMOJI_POOL)]}</a> <b>+{c}</b>'
                   for i, (uid, u, c) in enumerate(tags)]

    return terminal + "\n\n🎁 <b>Получили:</b> " + "  ".join(emoji_parts)


@router.message(F.text.regexp(r"^\+fire\s+(\d+(?:\.\d+)?)", flags=re.IGNORECASE))
async def cmd_fire(message: Message, container: Container):
    """{Visuals.fire_raw()} FIRE - Раздача монет участникам. Формат: +fire <кол-во> [валюта]"""
    username = message.from_user.username
    mention = f"@{username}" if username else f"<b>{html.escape(message.from_user.full_name)}</b>"

    # Команда теперь работает в любом чате, ограничение по settings.main_chat_id убрано.

    match = re.search(r"^\+fire\s+(\d+(?:\.\d+)?)(?:\s+([a-zA-Zа-яА-ЯёЁ]+))?", message.text or "", re.IGNORECASE)
    if not match:
        return

    try:
        coins = float(match.group(1))
        currency = match.group(2)

        # Если указана валюта, проверяем её
        if currency:
            normalized_currency = currency.lower()
            allowed = ["coin", "coins", "монет", "монеты", "монета", "c", "м"]
            if normalized_currency not in allowed:
                return

        if coins < 100:
            return await message.answer(f"{mention}\n\n{Visuals.cross()} Минимум для +fire: <b>100 монет</b>", parse_mode="HTML")
    except ValueError:
        return await message.answer(f"{mention}\n\n{Visuals.cross()} Неверный формат!", parse_mode="HTML")

    user_id = message.from_user.id
    is_admin = user_id in settings.admin_ids
    coins_int = int(round(coins))

    import time
    # Вычисляем время с момента запуска бота
    since_launch_hours = (time.time() - container.start_time) / 3600.0
    # Ищем активных за период с момента запуска (минимум 1 минута, чтобы не потерять тех кто только что написал)
    search_window = max(since_launch_hours, 1/60.0)

    try:
        # Сначала ищем тех, кто активничал с момента запуска
        recent_ids = await container.chat_activity_service.get_active_user_ids(message.chat.id, since_hours=search_window, limit=1000)
        exclude = set(settings.admin_ids) | {user_id}
        candidate_ids = list(recent_ids - exclude)

        # Если таких нет, выводим ошибку как просил пользователь
        if not candidate_ids:
            return await message.answer(
                f"{mention}\n\n{Visuals.cross()} <b>Активных должно быть больше!</b>\n"
                f"(с момента запуска активности не зафиксировано)",
                parse_mode="HTML"
            )

    except Exception as e:
        logger.exception(f"Ошибка получения пользователей: {e}")
        return await message.answer(f"{mention}\n\n{Visuals.cross()} Ошибка получения участников!", parse_mode="HTML")

    # Фильтруем пользователей по наличии в чате
    random.shuffle(candidate_ids)
    candidates = candidate_ids[:50]  # Проверяем до 50 кандидатов

    async def check_member(uid):
        try:
            member = await message.chat.get_member(uid)
            if member.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]:
                return {
                    'user_id': uid,
                    'username': member.user.username,
                    'first_name': member.user.first_name
                }
        except Exception:
            pass
        return None

    checked_results = await asyncio.gather(*[check_member(uid) for uid in candidates])
    recipients_pool = [u for u in checked_results if u]

    if not recipients_pool:
        return await message.answer(f"{mention}\n\n{Visuals.cross()} В этом чате нет активных участников для раздачи!", parse_mode="HTML")

    # Выбираем только ПОСЛЕДНИХ активных (от 5 до 10)
    min_count = min(5, len(recipients_pool))
    max_count = min(10, len(recipients_pool))
    num = random.randint(min_count, max_count)

    # Берем ПЕРВЫХ (последних активных) вместо random.sample
    recipients = recipients_pool[:num]

    # ОЧЕНЬ редко добавляем случайного юзера (5% шанс)
    if random.random() < 0.05 and len(recipients_pool) > num:
        lucky_user = random.choice([u for u in recipients_pool if u not in recipients])
        recipients.append(lucky_user)
        # Дополнительная монета для везучего
        coins_int += 1

    # Распределяем сумму
    per_user, rem = coins_int // len(recipients), coins_int % len(recipients)
    extra = random.sample(recipients, rem) if rem else []

    recipients_data = []
    tags = []

    for r in recipients:
        rid = r['user_id']
        amt = per_user + (1 if r in extra else 0)
        recipients_data.append((rid, amt))
        tags.append((rid, r.get('username'), amt))

    # Выполняем транзакцию через сервис
    try:
        result = await container.economy_service.fire_drop(
            sender_id=user_id,
            amount=coins_int,
            recipients_data=recipients_data,
            is_admin=is_admin
        )

        if not result["success"]:
            reason = result.get("reason", "unknown")
            if reason == "insufficient_funds":
                bal = result.get("balance", 0)
                return await message.answer(f"{mention}\n\n{Visuals.cross()} Недостаточно средств. У тебя {bal:,.2f}, нужно {coins_int:,}", parse_mode="HTML")
            elif reason == "insufficient_funds_bank":
                bal = result.get("balance", 0)
                return await message.answer(f"{mention}\n\n{Visuals.cross()} Недостаточно средств в банке. Баланс: {bal:,.2f}", parse_mode="HTML")
            else:
                return await message.answer(f"{mention}\n\n{Visuals.cross()} Ошибка операции: {reason}", parse_mode="HTML")

    except Exception as e:
        logger.exception(f"Ошибка выполнения fire drop: {e}")
        return await message.answer(f"{mention}\n\n{Visuals.cross()} Произошла ошибка при выполнении операции.", parse_mode="HTML")

    # Уведомление
    source = "🏦 БАНК Сенсея" if is_admin else "💳 Твой баланс"
    sender_name = mention # Use mention here

    try:
        msg = build_fire_drop_html(sender_name, is_admin, source, tags)
        await message.answer(msg, parse_mode="HTML")
    except Exception as e:
        logger.exception(f"Ошибка отправки уведомления: {e}")

    logger.info(f"{Visuals.fire_raw()} FIRE: {sender_name} раздал {coins_int:,} монет {len(tags)} участникам")