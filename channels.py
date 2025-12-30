# channels.py

class GuildConfig:
    def __init__(
            self,
            guild_id: int,
            open_category_id: int,
            claimed_category_id: int,
            closed_category_id: int,
            log_channel_id: int,
            team_role_id: int,
            admin_role_id: int | None = None,
            member_role_id: int | None = None,
            levelup_channel_id: int | None = None,
            lvl10: int | None = None,
            lvl25: int | None = None,
            lvl50: int | None = None,
            lvl100: int | None = None,
            vote_channel_id: int | None = None,
    ):
        self.guild_id = guild_id
        self.OPEN_CATEGORY_ID = open_category_id
        self.CLAIMED_CATEGORY_ID = claimed_category_id
        self.CLOSED_CATEGORY_ID = closed_category_id
        self.log_channel_id = log_channel_id
        self.team_role_id = team_role_id
        self.admin_role_id = admin_role_id
        self.member_role_id = member_role_id
        self.levelup_channel_id = levelup_channel_id
        self.lvl10 = lvl10
        self.lvl25 = lvl25
        self.lvl50 = lvl50
        self.lvl100 = lvl100
        self.vote_channel_id = vote_channel_id

HOUSE_OF_DEMONS = GuildConfig(
    guild_id=1181909214537461840,
    open_category_id=1454432353341538335,
    claimed_category_id=1454432402691854356,
    closed_category_id=1454432287667261667,
    log_channel_id=1305602441210757163,
    team_role_id=1185668409111879780,
    admin_role_id=1305594789466476545,
    member_role_id=1198641078191001662,
    levelup_channel_id=None,
    lvl10=1454435919112437770,
    lvl25=1454436115972100108,
    lvl50=1454436249854283776,
    lvl100=1454436333773914153,
    vote_channel_id=1454573899621859430,
)

NACHTBUS = GuildConfig(
    guild_id=1363137083148865598,
    open_category_id=1455652643488661738,
    claimed_category_id=1455653203994607792,
    closed_category_id=1455655553404764180,
    log_channel_id=1411140003874213948,
    team_role_id=1363149195279732829,
    admin_role_id=1363148778370240702,
    member_role_id=1363152209164107826,
    levelup_channel_id=None, #Leveling deaktiviert
    lvl10=None,
    lvl25=None,
    lvl50=None,
    lvl100=None,
    vote_channel_id=12
)

INFINITY_EMPIRE = GuildConfig(
    guild_id=1437819512798969990,
    open_category_id=1455672590642315295,
    claimed_category_id=1455672703767023820,
    closed_category_id=1455672540830761031,
    log_channel_id=1455672942104019198,
    team_role_id=1437820265814954117,
    admin_role_id=1437819823752216607,
    member_role_id=1437824535389802496,
    levelup_channel_id=None,
    lvl10=1455673508754362478,
    lvl25=1455673703693156585,
    lvl50=1455673792226529282,
    lvl100=1455673859373142199,
    vote_channel_id=1455674287095812282
)

ALL_GUILDS = {
    HOUSE_OF_DEMONS.guild_id: HOUSE_OF_DEMONS,
    NACHTBUS.guild_id: NACHTBUS,
    INFINITY_EMPIRE.guild_id: INFINITY_EMPIRE,
}

def get_config(guild_id: int) -> GuildConfig | None:
    return ALL_GUILDS.get(guild_id)
