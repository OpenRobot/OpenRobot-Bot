import discord
from discord.ui import View, Select, Button, button, select
from discord import ButtonStyle, SelectOption, Interaction

#class APIRequest(View):
#    def __init__(self, data: dict):
#        self.data = data
#        super().__init__(timeout=None)
#
#    @button(label='Reason', custom_id='api_request:reason', style=ButtonStyle.blurple)
#    async def reason(self, button: Button, interaction: Interaction):
#        await interaction.response.send_message(embed=discord.Embed(description=self.data['reason']))
#
#    @button(label='Info', custom_id='api_request:info', style=ButtonStyle.blurple)
#    async def info(self, button: Button, interaction: Interaction):
#        await interaction.response.send_message(embed=discord.Embed(description=self.data['info']))