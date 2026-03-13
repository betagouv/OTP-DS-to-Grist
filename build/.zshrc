# Activer la substitution dans le prompt
setopt PROMPT_SUBST

# Prompt avec emoji + branche git
PS1='%(?.🦄.⚡) %F{blue}%~%f$(git_branch) '

# Fonction pour afficher la branche git
git_branch() {
    local branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
    if [ -n "$branch" ]; then
        echo "($branch)"
    fi
}
