import base64
import io
import os
import traceback
import uuid
import zipfile
from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder
from palworld_save_pal.ws.messages import (
    DownloadSaveFileMessage,
    LoadSaveFileMessage,
    MessageType,
    UpdateSaveFileMessage,
    LoadZipFileMessage,
)
from palworld_save_pal.ws.utils import build_response
from palworld_save_pal.state import get_app_state
from palworld_save_pal.utils.logging_config import create_logger

logger = create_logger(__name__)


async def load_save_file_handler(message: LoadSaveFileMessage, ws: WebSocket):
    logger.info("Processing save file upload")

    async def ws_callback(message: str):
        response = build_response(MessageType.PROGRESS_MESSAGE, message)
        await ws.send_json(response)

    try:
        app_state = get_app_state()
        file_data = bytes(message.data)
        await app_state.process_save_file(file_data, ws_callback)
        data = {
            "name": app_state.save_file.name,
            "size": app_state.save_file.size,
        }
        logger.info("Save file loaded: %s", app_state.save_file.name)
        await ws_callback(
            "File uploaded and processed successfully, results coming right up!"
        )
        response = build_response(MessageType.LOAD_SAVE_FILE, data)
        await ws.send_json(response)
        data = jsonable_encoder(app_state.players)
        response = build_response(MessageType.GET_PLAYERS, data)
        await ws.send_json(response)

    except Exception as e:
        logger.error("Error processing save file: %s", str(e))
        response = build_response(MessageType.ERROR, f"Error processing file: {str(e)}")
        traceback.print_exc()
        await ws.send_json(response)


async def update_save_file_handler(message: UpdateSaveFileMessage, ws: WebSocket):
    logger.info("Processing save file update")

    async def ws_callback(message: str):
        response = build_response(MessageType.PROGRESS_MESSAGE, message)
        await ws.send_json(response)

    try:
        modified_pals = (
            message.data.modified_pals if message.data.modified_pals else None
        )
        modified_players = (
            message.data.modified_players if message.data.modified_players else None
        )
        app_state = get_app_state()
        save_file = app_state.save_file

        if not save_file:
            raise ValueError("No save file loaded")

        if modified_pals:
            await save_file.update_pals(modified_pals, ws_callback)
        if modified_players:
            await save_file.update_players(modified_players, ws_callback)

        app_state.players = save_file.get_players()
        response = build_response(MessageType.UPDATE_SAVE_FILE, "Changes saved")
        await ws.send_json(response)
        data = jsonable_encoder(app_state.players)
        response = build_response(MessageType.GET_PLAYERS, data)
        await ws.send_json(response)
    except Exception as e:
        logger.error("Error processing save file update: %s", str(e))
        response = build_response(
            MessageType.ERROR, f"Error processing changes: {str(e)}"
        )
        traceback.print_exc()
        await ws.send_json(response)


async def download_save_file_handler(_: DownloadSaveFileMessage, ws: WebSocket):
    logger.info("Processing save file download")

    async def ws_callback(message: str):
        response = build_response(MessageType.PROGRESS_MESSAGE, message)
        await ws.send_json(response)

    try:
        app_state = get_app_state()
        save_file = app_state.save_file

        if not save_file:
            raise ValueError("No save file loaded")
        await ws_callback("Compressing GVAS to sav 💪...")
        sav_file = save_file.sav()
        await ws_callback("Encoding sav file to base64 🤖, get ready here it comes...")
        encoded_data = base64.b64encode(sav_file).decode("utf-8")
        data = {
            "name": "Level.sav",
            "content": encoded_data,
        }
        logger.info("Generated save file and sending to client")
        response = build_response(MessageType.DOWNLOAD_SAVE_FILE, data)
        await ws.send_json(response)

    except Exception as e:
        logger.error("Error processing save file download: %s", str(e))
        response = build_response(
            MessageType.ERROR, f"Error downloading file: {str(e)}"
        )
        traceback.print_exc()
        await ws.send_json(response)


async def load_zip_file_handler(message: LoadZipFileMessage, ws: WebSocket):
    logger.info("Processing zip file upload")

    async def ws_callback(message: str):
        response = build_response(MessageType.PROGRESS_MESSAGE, message)
        await ws.send_json(response)

    try:
        app_state = get_app_state()
        zip_data = bytes(message.data)

        with zipfile.ZipFile(io.BytesIO(zip_data), "r") as zip_ref:
            file_list = zip_ref.namelist()
            if file_list is None:
                raise ValueError("Zip file is empty")

            save_id = file_list[0].split("/")[0]
            level_sav = f"{save_id}/Level.sav"

            if level_sav not in file_list:
                raise ValueError(
                    f"Zip file does not contain 'Level.sav', available files: {file_list}"
                )

            level_sav_data = zip_ref.read(level_sav)

            # Process player files
            player_files = [
                f
                for f in file_list
                if f.startswith(f"{save_id}/Players/") and f.endswith(".sav")
            ]
            player_data = {}
            for player_file in player_files:
                player_id = os.path.splitext(os.path.basename(player_file))[0]
                player_uuid = uuid.UUID(player_id)
                player_data[player_uuid] = zip_ref.read(player_file)

            await app_state.process_save_files(
                save_id, level_sav_data, player_data, ws_callback
            )

            # Here you would process the player data
            # For now, we'll just log it
            logger.info("Found %s player files", len(player_files))

        data = {
            "name": app_state.save_file.name,
            "size": app_state.save_file.size,
        }

        logger.info("Zip file processed: %s", app_state.save_file.name)
        await ws_callback(
            "Zip file uploaded and processed successfully, results coming right up!"
        )

        response = build_response(MessageType.LOAD_ZIP_FILE, data)
        await ws.send_json(response)

        data = jsonable_encoder(app_state.players)
        response = build_response(MessageType.GET_PLAYERS, data)
        await ws.send_json(response)

    except Exception as e:
        logger.error("Error processing zip file: %s", str(e))
        response = build_response(
            MessageType.ERROR, f"Error processing zip file: {str(e)}"
        )
        traceback.print_exc()
        await ws.send_json(response)
