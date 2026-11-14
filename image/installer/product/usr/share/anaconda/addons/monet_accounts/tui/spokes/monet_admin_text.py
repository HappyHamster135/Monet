"""Apply Monet's account requirement in Anaconda's text installer."""

from pyanaconda.core.i18n import _
from pyanaconda.ui.lib.users import get_user_list
from pyanaconda.ui.tui.spokes.user import UserSpoke

__all__ = ["MonetAdminTextSpoke"]


class MonetAdminTextSpoke(UserSpoke):
    mandatory = True

    @property
    def completed(self):
        return any(user.name and not user.lock and user.password and user.has_admin_priviledges()
                   for user in get_user_list(self._users_module))

    @property
    def status(self):
        if not self.completed:
            return _("Create an administrator with a password")
        return super().status
