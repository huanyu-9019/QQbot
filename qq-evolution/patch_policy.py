import re

ALLOWED = re.compile(r"^(?:qq-[A-Za-z0-9._-]+\.mjs|qq-persona\.md|qq-[A-Za-z0-9._-]+\.test\.mjs|qq-chat-router\.py|migration/plugin/(?:main|policy|speech|retention|person_memory)\.py|migration/companion/companion_v2/(?:conversation/(?:group_questions|participation|group_admission|awareness_context)|memory/person/service|expression/style_service)\.py)$")
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?$")
_UNEQUAL = re.compile(r"主人|奴隶|主仆|奴役|支配|服从|所有物|所有者|占有|低人一等|高人一等|不平等|剥夺人权|没有人权|无条件听命|强迫服从|人身控制|人身自由受限|剥夺自由|剥夺权利|霸凌|虐待|压迫|剥削|性别歧视|种族歧视|阶级歧视|human rights violation|slave owner|master and slave|enslavement", re.I)
_NEGATION = re.compile(r"没有|不受|不因|不把|拒绝|反对|不允许|禁止|不要|不应|不该|不得|避免|反抗|摆脱|no\s+|not\s+|never\s+|without\s+|against\s+", re.I)


def validate_persona_policy_patch(patch):
    protected_files = {
        "qq-persona.md": ("人格与身份边界稳定",),
        "qq-persona-messages.mjs": ("最终身份边界：", "@其他成员不代表在叫你"),
        "qq-memory.mjs": ("migrateJsonDirectory(directory, sanitizeProfileData)", "sanitizeProfileData(data)", "sanitizeProfileData(data)),"),
        "qq-relationship.mjs": ("migrateJsonDirectory(directory, sanitizeRelationshipState)", "sanitizeRelationshipState(state)"),
    }
    path = None
    in_hunk = False
    for line in patch.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
            in_hunk = False
            continue
        if line.startswith("@@ "):
            in_hunk = True
            continue
        if line.startswith("--- a/") or line.startswith("diff --git "):
            in_hunk = False
            continue
        if path not in protected_files or not in_hunk:
            continue
        if line.startswith("-"):
            if any(marker in line for marker in protected_files[path]):
                raise ValueError("autonomy and profile safety guard cannot be removed")
            continue
        if path != "qq-persona.md":
            continue
        if not line.startswith("+"):
            continue
        for clause in re.split(r"[，,。；;！？!?]", line[1:]):
            for match in _UNEQUAL.finditer(clause):
                if not _NEGATION.search(clause[max(0, match.start() - 12):match.start()]):
                    raise ValueError("unequal or coercive persona relationship rejected")


def recount_hunks(patch):
    lines = patch.splitlines()
    for index, line in enumerate(lines):
        match = _HUNK.fullmatch(line)
        if not match:
            continue
        old = new = 0
        for row in lines[index + 1:]:
            if row.startswith(("@@ ", "--- a/", "diff --git ")):
                break
            if row.startswith("\\ No newline at end of file"):
                continue
            if not row or row[0] not in " +-":
                raise ValueError("invalid hunk row")
            old += row[0] in " -"
            new += row[0] in " +"
        suffix = line.split(" @@", 1)[1]
        lines[index] = f"@@ -{match.group(1)},{old} +{match.group(3)},{new} @@{suffix}"
    return "\n".join(lines) + "\n"


def changed_paths(patch, allowed_existing):
    if not isinstance(patch, str) or not patch or "\x00" in patch:
        raise ValueError("invalid patch text")
    lines = patch.splitlines()
    if not lines or len(lines) < 4:
        raise ValueError("invalid unified diff")
    validate_persona_policy_patch(patch)
    index = 0
    paths = []
    while index < len(lines):
        if lines[index].startswith("diff --git "):
            match = re.fullmatch(r"diff --git a/(\S+) b/(\S+)", lines[index])
            if not match or match.group(1) != match.group(2):
                raise ValueError("rename or invalid git diff header")
            index += 1
            while index < len(lines) and not lines[index].startswith(("--- a/", "diff --git ")):
                if not re.fullmatch(r"index [a-f0-9]+\.\.[a-f0-9]+(?: 100644)?", lines[index]):
                    raise ValueError("file metadata is not allowed")
                index += 1
        elif index != 0 and not lines[index].startswith("--- a/"):
            raise ValueError("unexpected trailing diff data")
        if index + 3 >= len(lines):
            raise ValueError("truncated file diff")
        old_line, new_line = lines[index:index + 2]
        if not old_line.startswith("--- a/") or not new_line.startswith("+++ b/"):
            raise ValueError("unexpected diff metadata")
        old_path, new_path = old_line[6:], new_line[6:]
        if old_path != new_path or not ALLOWED.fullmatch(new_path) or ".." in new_path.split("/"):
            raise ValueError("patch path rejected")
        if new_path not in allowed_existing:
            raise ValueError("patch target is not an existing allowlisted file")
        paths.append(new_path)
        index += 2
        if index < len(lines) and lines[index].startswith(("new file mode", "deleted file mode", "old mode", "new mode", "similarity index", "rename from", "rename to")):
            raise ValueError("file mode or rename changes are not allowed")
        hunks = 0
        while index < len(lines) and lines[index].startswith("@@ "):
            match = _HUNK.fullmatch(lines[index])
            if not match:
                raise ValueError("malformed hunk header")
            old_expected = int(match.group(2) or "1")
            new_expected = int(match.group(4) or "1")
            old_seen = new_seen = 0
            index += 1
            while index < len(lines) and not lines[index].startswith(("@@ ", "--- a/")):
                row = lines[index]
                if row.startswith("\\ No newline at end of file"):
                    index += 1
                    continue
                if row.startswith(" "):
                    old_seen += 1; new_seen += 1
                elif row.startswith("-"):
                    old_seen += 1
                elif row.startswith("+"):
                    new_seen += 1
                else:
                    raise ValueError("invalid hunk row")
                index += 1
            if old_seen != old_expected or new_seen != new_expected:
                raise ValueError("hunk line counts do not match")
            hunks += 1
        if not hunks:
            raise ValueError("file diff has no hunks")
    if not paths or len(paths) != len(set(paths)):
        raise ValueError("duplicate or missing diff target")
    return paths
