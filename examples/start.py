#!/usr/bin/env python

import getpass
import sys
import re
from optparse import OptionParser

from minecraft import authentication
from minecraft.exceptions import YggdrasilError
from minecraft.networking.connection import Connection
from minecraft.networking.packets import Packet, clientbound, serverbound
from minecraft.networking.types import Vector


def get_options():
    """
    Using Pythons OptionParser, get the sys args and the corresponding
    input parsed as required until there is enough input to proceed.

    Returns
    -------
    options
        The options to run this instance with

    """
    parser = OptionParser()

    parser.add_option(
        "-u",
        "--username",
        dest="username",
        default=None,
        help="username to log in with",
    )

    parser.add_option(
        "-p",
        "--password",
        dest="password",
        default=None,
        help="password to log in with",
    )

    parser.add_option(
        "-s",
        "--server",
        dest="server",
        default=None,
        help="server host or host:port "
        "(enclose IPv6 addresses in square brackets)",
    )

    parser.add_option(
        "-o",
        "--offline",
        dest="offline",
        action="store_true",
        help="connect to a server in offline mode " "(no password required)",
    )

    parser.add_option(
        "-d",
        "--dump-packets",
        dest="dump_packets",
        action="store_true",
        help="print sent and received packets to standard error",
    )

    parser.add_option(
        "-v",
        "--dump-unknown-packets",
        dest="dump_unknown",
        action="store_true",
        help="include unknown packets in --dump-packets output",
    )

    parser.add_option(
        "-m",
        "--microsoft",
        dest="microsoft",
        action="store_true",
        help="Enable Microsoft Auth")

    (options, args) = parser.parse_args()

    if not options.microsoft:
        if not options.username:
            options.username = input("Enter your username: ")

        if not options.password and not options.offline:
            options.password = getpass.getpass("Enter your password (leave "
                                               "blank for offline mode): ")
            options.offline = options.offline or (options.password == "")

    if not options.server:
        options.server = input(
            "Enter server host or host:port "
            "(enclose IPv6 addresses in square brackets): "
        )
    # Try to split out port and address
    match = re.match(
        r"((?P<host>[^\[\]:]+)|\[(?P<addr>[^\[\]]+)\])" r"(:(?P<port>\d+))?$",
        options.server,
    )
    if match is None:
        raise ValueError("Invalid server address: '%s'." % options.server)
    options.address = match.group("host") or match.group("addr")
    options.port = int(match.group("port") or 25565)

    return options


def main():
    """Our main function for running the simple pyCraft implementation.

    This function handles and maintains:
     - Gaining authentication tokens & 'logging in'
     - Connecting to the provided server, online or offline
     - Prints the chat packet data to standard out on Clientbound Packet
     - Writes Serverbound chat Packets when required
     - Dumping all packets to standard out

    Notes
    -----
    This is a blocking function.

    """
    options = get_options()

    if options.offline:
        print("Connecting in offline mode...")
        connection = Connection(
            options.address, options.port, username=options.username
        )
    else:

        try:
            auth_token = authentication.Microsoft_AuthenticationToken()
            auth_token.authenticate()
        except YggdrasilError as e:
            print(e)
            sys.exit()
        print("Logged in as %s..." % auth_token.username)
        connection = Connection(
            options.address,
            options.port,
            auth_token,
            None,
            "1.8")

    if options.dump_packets:

        def print_incoming(packet):
            if type(packet) is Packet:
                # This is a direct instance of the base Packet type, meaning
                # that it is a packet of unknown type, so we do not print it
                # unless explicitly requested by the user.
                if options.dump_unknown:
                    print("--> [unknown packet] %s" % packet, file=sys.stderr)
            else:
                print("--> %s" % packet, file=sys.stderr)

        def print_outgoing(packet):
            print("<-- %s" % packet, file=sys.stderr)

        connection.register_packet_listener(print_incoming, Packet, early=True)
        connection.register_packet_listener(
            print_outgoing, Packet, outgoing=True)

    def handle_join_game(join_game_packet):
        print("Connected.")

    connection.register_packet_listener(
        handle_join_game, clientbound.play.JoinGamePacket
    )

    def print_chat(chat_packet):
        print(
            "Message (%s): %s"
            % (chat_packet.field_string("position"), chat_packet.json_data)
        )

    connection.register_packet_listener(
        print_chat, clientbound.play.ChatMessagePacket)


    def print_location(location_packet):
        print(
            "MapPacket (%s): %s"
            % (location_packet.field_string("position"), location_packet.json_data)
        )

    connection.register_packet_listener(
        print_location, clientbound.play.MapPacket)

    current_x_pos = float(-7.5)
    def print_postion(postion_packet):
        global current_x_pos
        current_x_pos = postion_packet.x
        print(
            "PositionPacket (%s): %s"
            % (postion_packet.field_string("position"), postion_packet.x)
        )

    connection.register_packet_listener(
        print_postion, clientbound.play.PlayerPositionAndLookPacket
    )

    connection.connect()

    count = 0
    while True:
        try:
            text = input()
            if text == "test":
                print(f"Testing, currentpos: {current_x_pos}")
                new_x = float(current_x_pos + 0.5)
                pos_packet = serverbound.play.PositionAndLookPacket()
                pos_packet.x = new_x
                pos_packet.feet_y = float(68.0)
                pos_packet.z = float(-1.5)
                pos_packet.yaw = 0.0
                pos_packet.pitch = 0.0
                pos_packet.on_ground = False
                connection.write_packet(pos_packet, force=True)
                current_x_pos = new_x

            else:
                print(f"Count2: {count}")
                packet = serverbound.play.ChatPacket()
                packet.message = text
                connection.write_packet(packet)
        except KeyboardInterrupt:
            print("Bye!")
            sys.exit()


if __name__ == "__main__":
    main()
