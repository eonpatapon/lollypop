# Copyright (c) 2014-2015 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk, GLib, GObject, Gdk
from cgi import escape
from gettext import gettext as _

from lollypop.define import Lp, Type, ArtSize, NextContext
from lollypop.pop_infos import InfosPopover
from lollypop.widgets_track import TracksWidget
from lollypop.objects import Track
from lollypop.widgets_rating import RatingWidget
from lollypop.pop_menu import AlbumMenu
from lollypop.pop_covers import CoversPopover
from lollypop.objects import Album


class AlbumWidget(Gtk.Bin):
    """
        Base album widget
    """

    def __init__(self, album_id, genre_id=None, preload=False):
        """
            Init widget
        """
        Gtk.Bin.__init__(self)
        self._album = Album(album_id, genre_id, preload=preload)
        self._selected = None
        self._stop = False
        self._cover = None

    def set_cover(self, force=False):
        """
            Set cover for album if state changed
            @param force as bool
        """
        selected = self._album.id == Lp.player.current_track.album.id
        if self._cover and (selected != self._selected or force):
            self._selected = selected
            surface = Lp.art.get_album(
                                self._album.id,
                                ArtSize.BIG * self._cover.get_scale_factor(),
                                selected)
            self._cover.set_from_surface(surface)
            del surface

    def update_cover(self, album_id):
        """
            Update cover for album id id needed
            @param album id as int
        """
        if self._cover and self._album.id == album_id:
            self._selected = self._album.id == Lp.player.current_track.album.id
            surface = Lp.art.get_album(
                                self._album.id,
                                ArtSize.BIG * self._cover.get_scale_factor(),
                                self._selected)
            self._cover.set_from_surface(surface)
            del surface

    def update_playing_indicator(self):
        """
            Update playing indicator
        """
        pass

    def update_cursor(self):
        """
            Update cursor for album
        """
        pass

    def stop(self):
        """
            Stop populating
        """
        self._stop = True

    def get_id(self):
        """
            Return album id for widget
            @return album id as int
        """
        return self._album.id

    def get_title(self):

        """
            Return album title
            @return album title as str
        """
        return self._album.name

#######################
# PRIVATE             #
#######################
    def _on_enter_notify(self, widget, event):
        """
            Add hover style
            @param widget as Gtk.Widget
            @param event es Gdk.Event
        """
        # https://bugzilla.gnome.org/show_bug.cgi?id=751076
        # See application.css => white
        self._cover.get_style_context().add_class('hovereffect')

    def _on_leave_notify(self, widget, event):
        """
            Remove hover style
            @param widget as Gtk.Widget
            @param event es Gdk.Event
        """
        # https://bugzilla.gnome.org/show_bug.cgi?id=751076
        # See application.css => white
        self._cover.get_style_context().remove_class('hovereffect')


class AlbumSimpleWidget(AlbumWidget):
    """
        Album widget showing cover, artist and title
    """

    def __init__(self, album_id):
        """
            Init simple album widget
            @param album id as int
        """
        AlbumWidget.__init__(self, album_id)
        self._eventbox = None

        builder = Gtk.Builder()
        builder.add_from_resource('/org/gnome/Lollypop/AlbumSimpleWidget.ui')
        builder.connect_signals(self)
        widget = builder.get_object('widget')
        self._cover = builder.get_object('cover')
        widget.set_property('has-tooltip', True)
        self._title_label = builder.get_object('title')
        self._title_label.set_text(self._album.name)
        self._artist_label = builder.get_object('artist')
        self._artist_label.set_text(self._album.artist_name)
        self.add(widget)
        self.set_cover()
        self.set_property('halign', Gtk.Align.START)

    def do_get_preferred_width(self):
        """
            Set maximum width
        """
        return self._cover.get_preferred_width()

    def update_cursor(self):
        """
            Update cursor for album
        """
        if self._eventbox is None:
            return
        window = self._eventbox.get_window()
        if window is None:
            return
        if Lp.settings.get_value('auto-play'):
            window.set_cursor(Gdk.Cursor(Gdk.CursorType.HAND1))
        else:
            window.set_cursor(Gdk.Cursor(Gdk.CursorType.LEFT_PTR))

#######################
# PRIVATE             #
#######################
    def _on_eventbox_realize(self, eventbox):
        """
            Change cursor over cover eventbox
            @param eventbox as Gdk.Eventbox
        """
        self._eventbox = eventbox
        if Lp.settings.get_value('auto-play'):
            eventbox.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.HAND1))

    def _on_query_tooltip(self, widget, x, y, keyboard, tooltip):
        """
            Show tooltip if needed
            @param widget as Gtk.Widget
            @param x as int
            @param y as int
            @param keyboard as bool
            @param tooltip as Gtk.Tooltip
        """
        layout_title = self._title_label.get_layout()
        layout_artist = self._artist_label.get_layout()
        if layout_title.is_ellipsized() or layout_artist.is_ellipsized():
            artist = escape(self._artist_label.get_text())
            title = escape(self._title_label.get_text())
            self.set_tooltip_markup("<b>%s</b>\n%s" % (artist, title))
        else:
            self.set_tooltip_text('')


class AlbumDetailedWidget(AlbumWidget):
    """
        Widget with cover and tracks
    """

    __gsignals__ = {
        'finished': (GObject.SignalFlags.RUN_FIRST, None, ())
    }

    try:
        from lollypop.wikipedia import Wikipedia
    except:
        Wikipedia = None

    def __init__(self, album_id, genre_id, pop_allowed, scrolled, size_group):
        """
            Init detailed album widget
            @param album id as int
            @param genre id as int
            @param parent width as int
            @param pop_allowed as bool if widget can show popovers
            @param scrolled as bool
            @param size group as Gtk.SizeGroup
        """
        AlbumWidget.__init__(self, album_id, genre_id=genre_id, preload=True)

        builder = Gtk.Builder()
        if scrolled:
            builder.add_from_resource(
                '/org/gnome/Lollypop/AlbumContextWidget.ui')
        else:
            builder.add_from_resource(
                '/org/gnome/Lollypop/AlbumDetailedWidget.ui')

        rating = RatingWidget(self._album)
        rating.show()
        builder.get_object('coverbox').add(rating)
        builder.connect_signals(self)

        if scrolled:
            builder.get_object('artist').set_text(self._album.artist_name)
            builder.get_object('artist').show()

        grid = builder.get_object('tracks')
        self._discs = self._album.discs
        self._tracks_left = {}
        self._tracks_right = {}
        show_label = len(self._discs) > 1
        i = 0
        for disc in self._discs:
            index = disc.number
            if show_label:
                label = Gtk.Label()
                label.set_text(_("Disc %s") % index)
                label.set_property('halign', Gtk.Align.START)
                label.get_style_context().add_class('dim-label')
                if i:
                    label.set_property('margin-top', 30)
                label.show()
                grid.attach(label, 0, i, 2, 1)
                i += 1
                sep = Gtk.Separator()
                sep.set_property('margin-bottom', 2)
                sep.show()
                grid.attach(sep, 0, i, 2, 1)
                i += 1
            self._tracks_left[index] = TracksWidget(pop_allowed)
            self._tracks_right[index] = TracksWidget(pop_allowed)
            grid.attach(self._tracks_left[index], 0, i, 1, 1)
            grid.attach(self._tracks_right[index], 1, i, 1, 1)
            size_group.add_widget(self._tracks_left[index])
            size_group.add_widget(self._tracks_right[index])

            self._tracks_left[index].connect('activated',
                                             self._on_activated)
            self._tracks_left[index].connect('button-press-event',
                                             self._on_button_press_event)
            self._tracks_right[index].connect('activated', self._on_activated)
            self._tracks_right[index].connect('button-press-event',
                                              self._on_button_press_event)

            self._tracks_left[index].show()
            self._tracks_right[index].show()
            i += 1

        self._cover = builder.get_object('cover')
        self.set_cover()

        builder.get_object('title').set_label(self._album.name)
        builder.get_object('year').set_label(self._album.year)
        self.add(builder.get_object('AlbumDetailedWidget'))

        if pop_allowed:
            self._menu = builder.get_object('menu')
            self._eventbox = builder.get_object('eventbox')
            self._eventbox.connect('realize', self._on_eventbox_realize)
            self._eventbox.connect("button-press-event",
                                   self._on_cover_press_event)
            self._menu.connect('clicked',
                               self._pop_menu)
            self._menu.show()
        else:
            self._eventbox = None

    def update_playing_indicator(self):
        """
            Update playing indicator
        """
        for disc in self._discs:
            self._tracks_left[disc.number].update_playing(
                Lp.player.current_track.id)
            self._tracks_right[disc.number].update_playing(
                Lp.player.current_track.id)

    def populate(self):
        """
            Populate tracks
            @thread safe
        """
        self._stop = False
        sql = Lp.db.get_cursor()
        for disc in self._discs:
            mid_tracks = int(0.5 + len(disc.tracks) / 2)
            self.populate_list_left(disc.tracks[:mid_tracks],
                                    disc,
                                    1)
            self.populate_list_right(disc.tracks[mid_tracks:],
                                     disc,
                                     mid_tracks + 1)
        sql.close()

    def populate_list_left(self, tracks, disc, pos):
        """
            Populate left list, thread safe
            @param tracks as [Track]
            @param disc as Disc
            @param pos as int
        """
        GLib.idle_add(self._add_tracks,
                      tracks,
                      self._tracks_left[disc.number],
                      pos)

    def populate_list_right(self, tracks, disc, pos):
        """
            Populate right list, thread safe
            @param tracks as [Track]
            @param disc as Disc
            @param pos as int
        """
        GLib.idle_add(self._add_tracks,
                      tracks,
                      self._tracks_right[disc.number],
                      pos)

    def update_cursor(self):
        """
            Update cursor for album
        """
        if self._eventbox is None:
            return
        window = self._eventbox.get_window()
        if window is None:
            return
        if Lp.settings.get_value('auto-play'):
            window.set_cursor(Gdk.Cursor(Gdk.CursorType.HAND1))
        else:
            window.set_cursor(Gdk.Cursor(Gdk.CursorType.PENCIL))

#######################
# PRIVATE             #
#######################
    def _pop_menu(self, widget):
        """
            Popup menu for album
            @param widget as Gtk.Button
            @param album id as int
        """
        pop_menu = AlbumMenu(self._album.id, self._album.genre_id)
        popover = Gtk.Popover.new_from_model(self._menu, pop_menu)
        popover.connect('closed', self._on_closed)
        self.get_style_context().add_class('album-menu-selected')
        popover.show()

    def _on_closed(self, widget):
        """
            Remove selected style
            @param widget as Gtk.Popover
        """
        self.get_style_context().remove_class('album-menu-selected')

    def _add_tracks(self, tracks, widget, i):
        """
            Add tracks for to tracks widget
            @param tracks as [(track_id, title, length, [artist ids])]
            @param widget as TracksWidget
            @param i as int
        """
        if not tracks or self._stop:
            self._stop = False
            # Emit finished signal if we are on the last disc for
            # the right tracks widget
            if widget == self._tracks_right[self._discs[-1].number]:
                self.emit('finished')
            return

        track = tracks.pop(0)

        # If we are listening to a compilation, prepend artist name
        title = escape(track.name)
        if self._album.artist_id == Type.COMPILATIONS or\
           len(track.artist_ids) > 1 or\
           self._album.artist_id not in track.artist_ids:
            if track.artist_names != self._album.artist_name:
                title = "<b>%s</b>\n%s" % (escape(track.artist_names),
                                           track.name)

        # Get track position in queue
        pos = None
        if Lp.player.is_in_queue(track.id):
            pos = Lp.player.get_track_position(track.id)

        if not Lp.settings.get_value('show-tag-tracknumber'):
            track_number = i
        else:
            track_number = track.number

        widget.add_track(track.id,
                         track_number,
                         title,
                         track.duration,
                         pos)

        GLib.idle_add(self._add_tracks, tracks, widget, i + 1)

    def _on_activated(self, widget, track_id):
        """
            On track activation, play track
            @param widget as TracksWidget
            @param track id as int
        """
        # Play track with no album, force repeat on track
        if self._button_state & Gdk.ModifierType.SHIFT_MASK:
            Lp.player.clear_albums()
            Lp.player.load(Track(track_id))
        else:
            Lp.player.context.next = NextContext.NONE
            if not Lp.player.is_party():
                Lp.player.set_albums(track_id,
                                     self._album.artist_id,
                                     self._album.genre_id)
            Lp.player.load(Track(track_id))
            if self._button_state & Gdk.ModifierType.CONTROL_MASK:
                Lp.player.context.next = NextContext.STOP_TRACK

    def _on_button_press_event(self, widget, event):
        """
            Keep track of mask
            @param widget as TrackWidget
            @param event as Gdk.Event
        """
        self._button_state = event.get_state()

    def _on_eventbox_realize(self, eventbox):
        """
            Change cursor over eventbox
            @param eventbox as Gdk.Eventbox
        """
        self.update_cursor()

    def _on_label_realize(self, eventbox):
        """
            Change pointer on label
            @param eventbox as Gtk.EventBox
        """
        if (Lp.lastfm is not None or self.Wikipedia is not None) and\
                self._album.artist_id != Type.COMPILATIONS:
            eventbox.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.HAND1))

    def _on_label_button_release(self, eventbox, event):
        """
            On clicked label, show artist informations in a popover
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        if (Lp.lastfm is not None or self.Wikipedia is not None) and\
                self._album.artist_id != Type.COMPILATIONS:
            popover = InfosPopover(self._album.artist_name)
            popover.set_relative_to(eventbox)
            popover.populate()
            popover.show()

    def _on_cover_press_event(self, widget, event):
        """
            Popover with album art downloaded from the web (in fact google :-/)
            @param: widget as Gtk.EventBox
            @param: event as Gdk.Event
        """
        show_popover = True
        if Lp.settings.get_value('auto-play'):
            if event.button == 1:
                show_popover = False
                Lp.player.play_album(self._album.id, self._album.genre_id)
        if show_popover:
            popover = CoversPopover(self._album.artist_id, self._album.id)
            popover.set_relative_to(widget)
            popover.populate()
            popover.show()
