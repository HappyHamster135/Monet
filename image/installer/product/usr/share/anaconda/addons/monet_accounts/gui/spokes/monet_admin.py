"""Require a usable administrator when installing Monet."""

from pyanaconda.core.i18n import _
from pyanaconda.ui.gui.spokes.user import UserSpoke
from pyanaconda.ui.lib.users import get_user_list

__all__ = ["MonetAdminSpoke"]


class MonetAdminSpoke(UserSpoke):
    # Anaconda treats any explicit Kickstart root setting as satisfying its
    # administrator check, including Monet's `rootpw --lock`.
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
