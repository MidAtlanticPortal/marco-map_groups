from django.contrib.auth.models import User, Group
from django.db import models
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404
from django.utils.crypto import get_random_string
from django.utils.text import slugify
from features.registry import enable_sharing


class MapGroupManager(models.Manager):
    def create(self, name, owner, open=False, blurb=''):
        """Creates a new map group with the specified options, owned by the
        specified user.

        @returns a tuple of (group, member)
        """
        mg = MapGroup()
        mg.name = name
        mg.blurb = blurb
        mg.owner = owner
        mg.is_open = open

        # Introduce a dependency on Groups so the Madrona feature sharing
        # will continue to work.
        name = mg._permission_group_name()
        pg = Group.objects.create(name=name)
        enable_sharing(pg)

        mg.permission_group = pg
        mg.save()

        # Add the owner to the new perm group
        owner.groups.add(pg)

        member = MapGroupMember()
        member.user = owner
        member.is_manager = True
        member.map_group = mg
        member.save()

        return mg, member


class MapGroupNonFeaturedManager(models.Manager):
    def get_queryset(self):
        qs = super(MapGroupNonFeaturedManager, self).get_queryset()
        qs = qs.filter(featuredgroups__isnull=True)
        return qs


class MapGroupFeaturedManager(models.Manager):
    def get_queryset(self):
        qs = super(MapGroupFeaturedManager, self).get_queryset()
        qs = qs.filter(featuredgroups__isnull=False)
        return qs


class MapGroup(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    owner = models.ForeignKey(User)
#     icon = models.URLField()
#     image = models.URLField()
    blurb = models.CharField(max_length=512)    # how long?
    permission_group = models.ForeignKey(Group, unique=True)
    
    is_open = models.BooleanField(default=False, help_text=("If false, users "
        "must be invited or request to join this group"))

    objects = MapGroupManager()
    not_featured = MapGroupNonFeaturedManager()
    featured = MapGroupFeaturedManager()

    def __str__(self):
        return "Map Group '%s'" % self.name

    def save(self, *args, **kwargs):
        self.slug = slugify(unicode(self.name))
        return super(MapGroup, self).save(*args, **kwargs)

    def rename(self, new_name):
        """Rename the mapgroup and it's associated permission group.
        """
        self.name = new_name
        self.save()
        self.permission_group.name = self._permission_group_name()
        self.permission_group.save()

    def get_absolute_url(self):
        return reverse('mapgroups:detail', kwargs={'pk': self.pk,
                                                    'slug': self.slug})

    def has_member(self, user):
        """@type user User
        """
        if user.is_anonymous() or not user.is_active:
            return False
        return self.mapgroupmember_set.filter(user=user).exists()

    def get_member(self, user):
        if user.is_anonymous() or not user.is_active:
            return None
        try:
            return self.mapgroupmember_set.get(user=user)
        except MapGroupMember.DoesNotExist:
            return None

    def _permission_group_name(self):
        """Compute the name of the permission group associated with this map
        group"""
        # The name is slug + 8 random chars
        # if the slug is >= 80 (Group.name max length), then replace the
        # last 8 chars with randomness.
        # This is done because slugs aren't guaranteed to be unique, but we
        # want permission groups to be unique to the map group.
        name = slugify(unicode(self.name))
        name = name[:min(80 - 8, len(name))] + get_random_string(8)
        return name


class MapGroupMember(models.Model):
    class Meta:
        unique_together = (('user', 'map_group',),)

    user = models.ForeignKey(User)
    map_group = models.ForeignKey(MapGroup)

    date_joined = models.DateTimeField(auto_now_add=True)
    
    # permissions
    # is_owner = models.BooleanField(default=False, help_text=("If true, this "
    #                                "user is the group's creator."))
    is_manager = models.BooleanField(default=False, help_text=("If true, this "
                                     "user may perform admin actions on this "
                                     "group"))

    # user-group-specific preferences
    show_real_name = models.BooleanField(default=False)

    def __str__(self):
        return "%s's Membership card for %s" % (self.user.first_name, self.map_group.name)

    def user_name_for_group(self):
        """Return the user's name as it should appear in this group.
        """
        if self.show_real_name:
            return self.user.get_full_name()
        else:
            return self.user.get_short_name()


class FeaturedGroupsManager(models.Manager):
    def get_queryset(self):
        return super(FeaturedGroupsManager, self).get_queryset().order_by('rank')


class FeaturedGroups(models.Model):
    rank = models.PositiveIntegerField(unique=True)
    # Note: unique FK here rather than 1:1, since the interface is a little
    # nicer in this case. You can say:
    # >>> mapgroup.featuredgroups_set.create(rank=4)
    # instead of:
    # >>> fg = FeaturedGroup.create(rank=4)
    # >>> mapgroup.featuredgroup = fg
    map_group = models.ForeignKey(MapGroup, unique=True)

    def __str__(self):
        return "#%d %s" % (self.rank, self.map_group.name)


class RecentActivityManager(models.Manager):
    def get_queryset(self):
        qs = super(RecentActivityManager, self).get_queryset()
        return qs.filter(date_created__lte=7)


# TODO: This isn't sufficient for admin messages
class ActivityLog(models.Model):
    """Record for events that have happened in this group.
    """
    
    group = models.ForeignKey(MapGroup)
    message = models.CharField(max_length=256)
    date_created = models.DateTimeField(auto_now_add=True)
    admin = models.BooleanField(default=False, help_text=("If true, this"
                                " message is only viewable by managers."))
    associated_user = models.ForeignKey(User, null=True, blank=True, 
                                        help_text=("The user this message is "
                                                   "associated with, if any."))

    recent = RecentActivityManager()
    objects = models.Manager()


class Invitation(models.Model):
    """A model to store user requests to join an invitation-only group, or 
    admin invitations to a user.
    
    User selects "Join group"
    If that group is "open"
    """
    user = models.ForeignKey(User)
    group = models.ForeignKey(MapGroup)
    message = models.CharField(max_length=512, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)


class EmailInvitation(models.Model):
    to_address = models.EmailField()
    map_group = models.ForeignKey(MapGroup)
    invite_code = models.CharField(max_length=32)
    invited_by = models.ForeignKey(MapGroupMember)
    date_sent = models.DateTimeField(auto_now_add=True)



