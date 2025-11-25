// Social Media Footer - Shared functionality
(function() {
    function initSocialFooter() {
        const cfg = window.FPP_CONFIG || {};
        const footer = document.getElementById('socialFooter');
        if (!footer) return;

        const icons = [
            { key: 'socialFacebook', icon: '📘', label: 'Facebook' },
            { key: 'socialInstagram', icon: '📷', label: 'Instagram' },
            { key: 'socialTiktok', icon: '🎵', label: 'TikTok' },
            { key: 'socialWhatsapp', icon: '💬', label: 'WhatsApp' },
            { key: 'socialChannels', icon: '📢', label: 'Channels' },
            { key: 'socialYoutube', icon: '▶️', label: 'YouTube' },
            { key: 'socialWebsite', icon: '🌐', label: 'Website' },
            { key: 'socialEmail', icon: '✉️', label: 'E-Mail', isEmail: true }
        ];

        let hasAny = false;
        icons.forEach(function(item) {
            const val = cfg[item.key];
            if (val) {
                hasAny = true;
                const a = document.createElement('a');
                a.href = item.isEmail ? 'mailto:' + val : val;
                a.target = item.isEmail ? '_self' : '_blank';
                a.rel = 'noopener noreferrer';
                a.className = 'social-icon';
                a.title = item.label;
                a.textContent = item.icon;
                footer.appendChild(a);
            }
        });

        if (!hasAny) {
            footer.style.display = 'none';
        }
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initSocialFooter);
    } else {
        initSocialFooter();
    }
})();
